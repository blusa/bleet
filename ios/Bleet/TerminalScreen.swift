import SwiftUI
import SwiftTerm

@MainActor @Observable final class TerminalSession {
    var status = "Connecting…"
    weak var view: TerminalView?
    private var socket: URLSessionWebSocketTask?
    private var receiver: Task<Void, Never>?
    private var cols = 80
    private var rows = 24
    private var started = false
    func connect(client: APIClient, server: String, host: String, mode: String) {
        guard !started else { return }; started = true
        do {
            let socket = try client.terminal(server: server, host: host, mode: mode)
            self.socket = socket; socket.resume()
            receiver = Task { [weak self] in
                guard let self else { return }
                do {
                    while !Task.isCancelled {
                        let message = try await socket.receive()
                        let data: Data
                        switch message { case .data(let value): data = value; case .string(let value): data = Data(value.utf8); @unknown default: continue }
                        let frame = try JSONDecoder().decode(TerminalFrame.self, from: data)
                        if frame.type == "output", let text = frame.data { self.status = "Connected · PTY"; self.view?.feed(text: text) }
                        else if frame.type == "exit" { self.status = "Session ended (\(frame.status ?? 0))"; self.close(); break }
                        else if frame.type == "error" { self.status = "Remote session unavailable"; self.close(); break }
                    }
                } catch { if !Task.isCancelled { self.status = "Disconnected · check your private connection" }; self.close() }
            }
            resize(cols: cols, rows: rows)
        } catch { status = "Could not authorize terminal connection" }
    }
    func resize(cols: Int, rows: Int) {
        self.cols = max(2, cols); self.rows = max(2, rows)
        send(TerminalFrame(type: "resize", cols: self.cols, rows: self.rows))
    }
    func input(_ data: ArraySlice<UInt8>) { send(TerminalFrame(type: "input", data: String(decoding: data, as: UTF8.self))) }
    private func send(_ frame: TerminalFrame) {
        guard let socket, let data = try? JSONEncoder().encode(frame), let text = String(data: data, encoding: .utf8) else { return }
        Task { [weak self] in
            do { try await socket.send(.string(text)) }
            catch { self?.status = "Disconnected · input was not sent"; self?.close() }
        }
    }
    func close() { receiver?.cancel(); receiver = nil; socket?.cancel(with: .goingAway, reason: nil); socket = nil }
}
struct TerminalScreen: View {
    let store: AppStore
    let host: Host
    let mode: String
    @State private var session = TerminalSession()
    @State private var fontSize: CGFloat = 13
    @State private var fitColumns: Bool
    @Environment(\.dismiss) private var dismiss
    init(store: AppStore, host: Host, mode: String) {
        self.store = store; self.host = host; self.mode = mode
        _fitColumns = State(initialValue: mode == "monitor")
    }
    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                HStack(spacing: 12) {
                    Circle().fill(session.status.hasPrefix("Connected") ? BleetStyle.mint : .orange).frame(width: 6, height: 6)
                    Text(session.status).font(.caption)
                    Spacer()
                    Menu("Text size", systemImage: "textformat.size") {
                        Button("Fit 80 columns", systemImage: "arrow.left.and.right") { fitColumns = true }
                        Button("Larger text", systemImage: "plus.magnifyingglass") { fitColumns = false; fontSize = min(24, fontSize + 1) }
                        Button("Smaller text", systemImage: "minus.magnifyingglass") { fitColumns = false; fontSize = max(7, fontSize - 1) }
                    }.labelStyle(.iconOnly)
                    Button("Hide keyboard", systemImage: "keyboard.chevron.compact.down") { _ = session.view?.resignFirstResponder() }.labelStyle(.iconOnly)
                }.foregroundStyle(.secondary).padding(12)
                GeometryReader { geometry in
                    NativeTerminal(session: session, fontSize: fitColumns ? fittedFont(width: geometry.size.width) : fontSize)
                        .background(.black).accessibilityLabel("Interactive SSH terminal")
                }
            }.navigationTitle("\(host.name) · \(mode == "monitor" ? "Monitor" : "Terminal")").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Disconnect") { session.close(); dismiss() } } }
        }
        .onAppear { session.connect(client: store.client, server: store.server, host: host.id, mode: mode) }
        .onDisappear { session.close() }
    }
    private func fittedFont(width: CGFloat) -> CGFloat {
        let reference = UIFont.monospacedSystemFont(ofSize: 13, weight: .regular)
        let cell = ("M" as NSString).size(withAttributes: [.font: reference]).width
        return max(6, min(13, floor(13 * max(1, width - 8) / (80 * cell) * 2) / 2))
    }
}
struct NativeTerminal: UIViewRepresentable {
    let session: TerminalSession
    let fontSize: CGFloat
    func makeCoordinator() -> Coordinator { Coordinator(session: session) }
    func makeUIView(context: Context) -> TerminalView {
        let view = TerminalView(frame: .zero, font: .monospacedSystemFont(ofSize: fontSize, weight: .regular))
        view.nativeBackgroundColor = .black
        view.nativeForegroundColor = UIColor(red: 0.82, green: 0.91, blue: 0.87, alpha: 1)
        view.terminalDelegate = context.coordinator
        session.view = view
        return view
    }
    func updateUIView(_ view: TerminalView, context: Context) {
        if view.font.pointSize != fontSize { view.font = .monospacedSystemFont(ofSize: fontSize, weight: .regular) }
    }
    static func dismantleUIView(_ view: TerminalView, coordinator: Coordinator) { coordinator.session.close(); view.terminalDelegate = nil }
    @MainActor final class Coordinator: NSObject, @preconcurrency TerminalViewDelegate {
        let session: TerminalSession
        init(session: TerminalSession) { self.session = session }
        func sizeChanged(source: TerminalView, newCols: Int, newRows: Int) { session.resize(cols: newCols, rows: newRows) }
        func send(source: TerminalView, data: ArraySlice<UInt8>) { session.input(data) }
        func setTerminalTitle(source: TerminalView, title: String) {}
        func hostCurrentDirectoryUpdate(source: TerminalView, directory: String?) {}
        func scrolled(source: TerminalView, position: Double) {}
        func requestOpenLink(source: TerminalView, link: String, params: [String: String]) {}
        func bell(source: TerminalView) {}
        func clipboardCopy(source: TerminalView, content: Data) {}
        func clipboardRead(source: TerminalView) -> Data? { nil }
        func iTermContent(source: TerminalView, content: ArraySlice<UInt8>) {}
        func rangeChanged(source: TerminalView, startY: Int, endY: Int) {}
    }
}
