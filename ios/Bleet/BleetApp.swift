import SwiftUI

@main struct BleetApp: App {
    @State private var store = AppStore()
    @Environment(\.scenePhase) private var scenePhase
    var body: some Scene {
        WindowGroup {
            RootView(store: store)
                .tint(BleetStyle.mint)
                .preferredColorScheme(.dark)
                .onOpenURL { store.deepLink($0) }
                .onChange(of: scenePhase, initial: true) { _, phase in store.active(phase == .active) }
        }
    }
}
struct RootView: View {
    @Bindable var store: AppStore
    var body: some View {
        GeometryReader { geometry in
            if store.snapshot == nil && !store.authenticated {
                WelcomeView(store: store)
            } else if geometry.size.width >= 700 {
                NavigationSplitView {
                    HostList(store: store)
                        .navigationTitle("")
                        .navigationBarTitleDisplayMode(.inline)
                        .toolbar {
                            ToolbarItem(placement: .principal) { BleetWordmark(compact: true) }
                            ToolbarItem(placement: .bottomBar) { settingsButton }
                        }
                } detail: {
                    NavigationStack { HostDashboard(store: store, wide: true).toolbar { settingsButton } }
                }
                .navigationSplitViewStyle(.balanced)
            } else {
                NavigationStack {
                    HostDashboard(store: store, wide: false)
                        .toolbar { settingsButton }
                }
            }
        }
        .background(BleetStyle.background)
        .sheet(isPresented: $store.settingsPresented) { ConnectionView(store: store) }
        .sheet(item: $store.pairing) { pairing in PairingView(pairing: pairing) }
        .fullScreenCover(item: $store.terminalHost) { host in TerminalScreen(store: store, host: host, mode: store.terminalMode) }
    }
    var settingsButton: some View { Button("Connection", systemImage: "network") { store.settingsPresented = true } }
}
struct WelcomeView: View {
    @Bindable var store: AppStore
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                BleetWordmark().padding(.top, 50)
                VStack(alignment: .leading, spacing: 12) {
                    Text("Your fleet.\nWithin reach.").font(.system(size: 42, weight: .medium, design: .rounded))
                    Text("Hardware, workloads and a real terminal. A quiet view into your private machines.").font(.title3).foregroundStyle(.secondary)
                }
                Button { store.settingsPresented = true } label: { Label("Connect your gateway", systemImage: "lock.shield").frame(maxWidth: .infinity).padding(10) }.buttonStyle(.borderedProminent).foregroundStyle(.black)
                Button { store.exploreDemo() } label: { Label("Explore demo fleet", systemImage: "square.grid.2x2").frame(maxWidth: .infinity) }.buttonStyle(.bordered)
                Text("Demo exploration uses bundled example readings. Your gateway stays private over your VPN.").font(.footnote).foregroundStyle(.secondary)
            }.padding(28).frame(maxWidth: 560)
        }.frame(maxWidth: .infinity).background(BleetStyle.background)
    }
}
struct HostList: View {
    @Bindable var store: AppStore
    @State private var search = ""
    var body: some View {
        List {
            if store.demo { Section { Label("Demo fleet", systemImage: "square.grid.2x2").foregroundStyle(BleetStyle.mint) } }
            ForEach((store.snapshot?.hosts ?? []).filter { search.isEmpty || $0.name.localizedCaseInsensitiveContains(search) }) { host in
                Button { store.select(host) } label: {
                    HStack {
                        Image(systemName: host.status == "online" ? "circle.fill" : "exclamationmark.circle").font(.caption2).foregroundStyle(host.status == "online" ? BleetStyle.mint : .orange)
                        VStack(alignment: .leading, spacing: 4) { Text(host.name).fontWeight(.medium); Text(host.source ?? "Private network").font(.caption).foregroundStyle(.secondary) }
                        Spacer()
                        if store.selection.hostID == host.id { Image(systemName: "checkmark").font(.caption).foregroundStyle(BleetStyle.mint) }
                    }.padding(.vertical, 5)
                }.foregroundStyle(.primary)
            }
        }.searchable(text: $search, prompt: "Find a machine")
    }
}
struct HostDashboard: View {
    @Bindable var store: AppStore
    let wide: Bool
    @State private var details = false
    @Environment(\.dynamicTypeSize) private var typeSize
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 22) {
                if store.demo { Label("DEMO · Example hardware and readings", systemImage: "square.grid.2x2").font(.caption).foregroundStyle(BleetStyle.mint) }
                if !wide { hostPicker }
                if let host = store.host {
                    header(host)
                    if let error = store.error { notice(error, symbol: "wifi.exclamationmark") }
                    if Snapshot.isStale(host.metrics?.collectedAt) { notice(store.demo ? "Example snapshot · not a live connection" : "Saved reading · status is unverified", symbol: "clock") }
                    if host.metricsError != nil { notice("The collector could not read this host. Previous readings may be shown.", symbol: "exclamationmark.triangle") }
                    if let metrics = host.metrics {
                        instrumentGrid(metrics)
                        memory(metrics)
                        if let core = metrics.cpu?.cores?.first(where: { $0.id == store.selection.coreID }) {
                            HStack { Text("Core \(core.index.map(String.init) ?? core.id)"); Spacer(); Text(MetricFormat.percent(core.usagePercent)).foregroundStyle(BleetStyle.mint) }.font(.subheadline)
                            Text("Logical CPUs: \(core.logicalIds?.map(String.init).joined(separator: ", ") ?? "Topology unavailable")").font(.caption).foregroundStyle(.secondary)
                        }
                    } else { ContentUnavailableView("Metrics unavailable", systemImage: "waveform.path", description: Text("This host has no current hardware reading.")) }
                    actions(host)
                    if store.desk { VStack(alignment: .leading, spacing: 12) { Label("Desk layout", systemImage: "rectangle.bottomhalf.inset.filled").font(.headline); Text("Open the monitor below. Bleet preserves your machine and resource selections while the window changes.").font(.subheadline).foregroundStyle(.secondary); Button("Open interactive monitor", systemImage: "terminal") { openTerminal(host, "monitor") }.disabled(store.demo) }.card() }
                    Button("Hardware & exact values", systemImage: "info.circle") { details = true }.font(.subheadline)
                    activity
                    Text("\(store.snapshot?.hosts.count ?? 0) machines · Refreshes every 8 seconds while active").font(.caption2).foregroundStyle(.secondary)
                } else {
                    ContentUnavailableView("Waiting for your fleet", systemImage: "server.rack", description: Text(store.error ?? "Connect to the private gateway to load your machines."))
                }
            }.padding(wide ? 28 : 20).frame(maxWidth: 1000)
        }.frame(maxWidth: .infinity).background(BleetStyle.background)
            .navigationTitle(wide ? (store.host?.name ?? "Fleet") : "")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { if !wide { ToolbarItem(placement: .principal) { BleetWordmark(compact: true) } } }
            .refreshable { await store.refresh() }
            .sheet(isPresented: $details) { HardwareView(host: store.host) }
    }
    var hostPicker: some View {
        Menu {
            ForEach(store.snapshot?.hosts ?? []) { host in Button(host.name) { store.select(host) } }
        } label: { HStack { Label(store.host?.name ?? "Choose machine", systemImage: "server.rack").font(.title2.weight(.semibold)); Image(systemName: "chevron.down").font(.caption); Spacer() }.foregroundStyle(.primary) }
        .accessibilityLabel("Selected host, \(store.host?.name ?? "none")")
    }
    func header(_ host: Host) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 8) {
                Label(host.status?.capitalized ?? "Unknown", systemImage: host.status == "online" ? "circle.fill" : "questionmark.circle").foregroundStyle(host.status == "online" ? BleetStyle.mint : .orange)
                Text("· \(host.metrics?.platform?.capitalized ?? host.source ?? "Private network")").foregroundStyle(.secondary)
            }.font(.subheadline)
            HStack(spacing: 16) { Text("Network: \(state(host.networkOnline))"); Text("SSH: \(state(host.sshOnline))") }.font(.caption).foregroundStyle(.secondary)
            if let date = Snapshot.date(host.metrics?.collectedAt) { Text("Measured \(date.formatted(date: .abbreviated, time: .standard))").font(.caption).foregroundStyle(.secondary) }
        }
    }
    func state(_ online: Bool?) -> String { online.map { $0 ? "reachable" : "unreachable" } ?? "unknown" }
    func notice(_ value: String, symbol: String) -> some View { Label(value, systemImage: symbol).font(.caption).foregroundStyle(.orange).frame(maxWidth: .infinity, alignment: .leading).padding(12).background(.orange.opacity(0.07), in: RoundedRectangle(cornerRadius: 10)) }
    func instrumentGrid(_ metrics: Metrics) -> some View {
        VStack(spacing: 12) {
            if !wide, let gpus = metrics.gpus, gpus.count > 1 {
                Picker("GPU", selection: Binding(get: { store.gpu?.id ?? "" }, set: { store.selection.gpuID = $0 })) { ForEach(gpus) { gpu in Text(gpu.label).tag(gpu.id) } }.pickerStyle(.segmented)
            }
            LazyVGrid(columns: [GridItem(.adaptive(minimum: typeSize.isAccessibilitySize ? 270 : (wide ? 180 : 140)), spacing: 12)], alignment: .leading, spacing: 12) {
                VStack(alignment: .leading, spacing: 12) {
                    HStack { Text("CPU").font(.headline); Spacer(); Text(MetricFormat.percent(metrics.cpu?.usagePercent)).font(.caption).foregroundStyle(BleetStyle.mint) }
                    Text(metrics.cpu?.name ?? "Unknown processor").font(.caption).foregroundStyle(.secondary).frame(minHeight: 32, alignment: .top)
                    if let cores = metrics.cpu?.cores, !cores.isEmpty { CPUHeatmap(cores: cores, selected: store.selection.coreID) { store.selection.coreID = $0 }.frame(maxWidth: 220).frame(maxWidth: .infinity) } else { Text("Per-core load unavailable").font(.caption).foregroundStyle(.secondary).frame(height: 112) }
                    Text(metrics.cpu?.cores.map { "\($0.count) \(metrics.cpu?.topologyLabel ?? "cores")" } ?? "Core topology unavailable").font(.caption2).foregroundStyle(.secondary)
                }.card()
                ForEach((metrics.gpus ?? []).filter { wide || $0.id == store.gpu?.id }) { gpu in
                    Button { store.selection.gpuID = gpu.id } label: {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack { Text(gpu.label).font(.headline); Spacer(); if gpu.id == store.gpu?.id { Image(systemName: "checkmark.circle.fill").foregroundStyle(BleetStyle.mint).font(.caption) } }
                            Text(gpu.name ?? "Unknown GPU").font(.caption).foregroundStyle(.secondary).frame(minHeight: 32, alignment: .top)
                            GPUGauge(usage: gpu.usagePercent).frame(maxHeight: 150).frame(maxWidth: .infinity)
                            Text(gpu.usesUnifiedMemory ? "Shared unified memory" : "\(MetricFormat.bytes(gpu.memoryTotalBytes)) VRAM").font(.caption2).foregroundStyle(.secondary)
                        }.card().overlay { RoundedRectangle(cornerRadius: 18).stroke(gpu.id == store.gpu?.id ? BleetStyle.mint.opacity(0.45) : .clear, lineWidth: 1) }
                    }.buttonStyle(.plain)
                }
            }
        }
    }
    func memory(_ metrics: Metrics) -> some View {
        VStack(spacing: 22) {
            MemoryBar(title: metrics.memory?.kind == "unified" ? "Unified memory" : "RAM", used: metrics.memory?.usedBytes, total: metrics.memory?.totalBytes)
            if let gpu = store.gpu, !gpu.usesUnifiedMemory, metrics.memory?.kind != "unified" { MemoryBar(title: "VRAM · \(gpu.label)", used: gpu.memoryUsedBytes, total: gpu.memoryTotalBytes) }
        }.card()
    }
    func actions(_ host: Host) -> some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                Button { openTerminal(host, "monitor") } label: { Label("Monitor", systemImage: "waveform.path.ecg").frame(maxWidth: .infinity).padding(.vertical, 6) }.buttonStyle(.borderedProminent).foregroundStyle(.black)
                Button { openTerminal(host, "shell") } label: { Label("Terminal", systemImage: "terminal").frame(maxWidth: .infinity).padding(.vertical, 6) }.buttonStyle(.bordered)
            }.disabled(store.demo)
            HStack {
                if let string = host.t3Url, let url = URL(string: string), url.scheme == "https" { Link("Open T3", destination: url).disabled(store.demo) }
                Button { Task { await store.pair() } } label: { Label(store.pairingBusy ? "Pairing…" : "Pair T3 Code", systemImage: "qrcode") }.disabled(store.demo || store.pairingBusy || !(host.isT3 == true || host.capabilities?.contains("t3") == true))
                Spacer()
                Toggle("Desk", isOn: $store.desk).toggleStyle(.button).font(.caption)
            }.font(.subheadline)
        }
    }
    func openTerminal(_ host: Host, _ mode: String) { store.terminalMode = mode; store.terminalHost = host }
    var activity: some View {
        VStack(alignment: .leading, spacing: 10) {
            if let errors = store.snapshot?.errors, !errors.isEmpty { Text("Source health").font(.headline); ForEach(Array(errors.enumerated()), id: \.offset) { _, item in Label(item.source.map { "\($0): source unavailable" } ?? "A source is unavailable", systemImage: "exclamationmark.triangle").font(.caption).foregroundStyle(.orange) } }
            if let events = store.snapshot?.events, !events.isEmpty { Text("Activity").font(.headline); ForEach(Array(events.prefix(8).enumerated()), id: \.offset) { _, event in Text(event.message ?? event.type ?? "Host status changed").font(.caption).foregroundStyle(.secondary) } }
        }
    }
}
extension View {
    func card() -> some View { self.padding(16).frame(maxWidth: .infinity, alignment: .leading).background(BleetStyle.panel, in: RoundedRectangle(cornerRadius: 18)) }
}


/// One accessible brand label; the nine squares are purely decorative.
struct BleetWordmark: View {
    var compact = false
    @ScaledMetric(relativeTo: .title) private var scale: CGFloat = 1
    private let tones: [Double] = [0.34, 0.58, 0.78, 0.52, 1, 0.68, 0.78, 0.60, 0.92]
    private var em: CGFloat { (compact ? 21 : 42) * scale }
    var body: some View {
        HStack(spacing: em * 0.28) {
            Grid(horizontalSpacing: em * 0.055, verticalSpacing: em * 0.055) {
                ForEach(0..<3) { row in
                    GridRow {
                        ForEach(0..<3) { column in
                            RoundedRectangle(cornerRadius: em * 0.045)
                                .fill(BleetStyle.mint.opacity(tones[row * 3 + column]))
                                .frame(width: em * 0.25, height: em * 0.25)
                        }
                    }
                }
            }.accessibilityHidden(true)
            Text("bleet")
                .font(.system(size: em, weight: .semibold, design: .rounded))
                .tracking(-em * 0.025)
                .foregroundStyle(.primary)
        }
        .fixedSize()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Bleet")
    }
}
