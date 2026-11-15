import SwiftUI

struct ConnectionView: View {
    @Bindable var store: AppStore
    @Environment(\.dismiss) private var dismiss
    @State private var busy = false
    @State private var error: String?
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("HTTPS gateway", text: $store.server).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("One-time enrollment code", text: $store.enrollmentCode).textContentType(.oneTimeCode).textInputAutocapitalization(.never).autocorrectionDisabled()
                    Button(busy ? "Connecting…" : "Enroll this device") {
                        busy = true; error = nil
                        Task {
                            defer { busy = false; store.enrollmentCode = "" }
                            do { try await store.enroll(code: store.enrollmentCode) }
                            catch { self.error = (error as? APIError)?.localizedDescription ?? APIError.unavailable.localizedDescription }
                        }
                    }.disabled(busy || store.enrollmentCode.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } header: { Text("Private gateway") } footer: { Text("Use the single-use code from your gateway administrator. Credentials are stored only in this device’s Keychain. Your VPN must provide a route to the gateway.") }
                if let error { Section { Text(error).foregroundStyle(.orange) } }
                Section("Connection") {
                    LabeledContent("Mode", value: store.demo ? "Demo exploration" : (store.authenticated ? "Enrolled device" : "Not enrolled"))
                    if let date = Snapshot.date(store.snapshot?.collectedAt) { LabeledContent("Last snapshot", value: date.formatted()) }
                    if store.authenticated { Button("Use enrolled gateway") { store.demo = false; store.settingsPresented = false; Task { await store.refresh() } }; Button("Remove device credential", role: .destructive) { store.disconnect() } }
                }
                Section { Button("Explore demo fleet", systemImage: "square.grid.2x2") { store.exploreDemo() } } footer: { Text("Bundled example readings. Terminal and pairing are available after enrollment.") }
                Section("About Bleet") {
                    NavigationLink("Privacy") { PrivacyView() }
                    Link("Support & source", destination: URL(string: "https://github.com/blusa/bleet")!)
                }
            }.navigationTitle("Connect Bleet").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { store.enrollmentCode = ""; dismiss() } } }
        }
        .onDisappear { store.enrollmentCode = "" }
    }
}
struct PrivacyView: View {
    var body: some View {
        List {
            Section("Your gateway") { Text("Bleet connects to the HTTPS gateway you choose. That gateway receives enrollment requests, hardware readings, terminal traffic and explicit T3 pairing requests. Your gateway administrator controls its hosts, access and retention.") }
            Section("On this device") { Text("Your device credential stays in Keychain. The app shares only the last hardware snapshot and its measurement time with its widgets. Remove the credential in Connection to clear local access and the widget snapshot; ask your gateway administrator to revoke server access.") }
            Section("Temporary pairing") { Text("T3 pairing links and QR codes are credentials. Bleet shows them temporarily and does not save or copy them. Opening a pairing page sends the link to your chosen browser and T3 service, which can retain it until expiry.") }
            Section("No tracking") { Text("Bleet includes no advertising, analytics or third-party AI service. Demo readings are bundled examples. Optional shell sessions execute as the gateway’s configured SSH user.") }
        }.navigationTitle("Privacy").navigationBarTitleDisplayMode(.inline)
    }
}
struct PairingView: View {
    let pairing: Pairing
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    Text("Pair T3 Code").font(.largeTitle.weight(.medium))
                    Text("Scan this temporary code with your T3 client, or open the pairing page.").multilineTextAlignment(.center).foregroundStyle(.secondary)
                    if let base64 = pairing.qrPngBase64, let data = Data(base64Encoded: base64), let image = UIImage(data: data) { Image(uiImage: image).interpolation(.none).resizable().scaledToFit().frame(maxWidth: 280).padding(16).background(.white, in: RoundedRectangle(cornerRadius: 16)).accessibilityLabel("Temporary T3 pairing QR code") }
                    if let string = pairing.pairingUrl, let url = URL(string: string), url.scheme == "https" { Link("Open temporary pairing page", destination: url).buttonStyle(.borderedProminent).foregroundStyle(.black) }
                    if let date = Snapshot.date(pairing.expiresAt) { Text("Expires \(date.formatted())").font(.caption).foregroundStyle(.secondary) }
                    Text("The pairing credential is shown only in this temporary view. Dismissing it removes it from Bleet’s view state.").font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }.padding(28)
            }.navigationTitle("T3 pairing").navigationBarTitleDisplayMode(.inline)
                .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }.privacySensitive()
    }
}
struct HardwareView: View {
    let host: Host?
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section("Host") { LabeledContent("Name", value: host?.name ?? "Unknown"); LabeledContent("Address", value: host?.address ?? "Unknown"); LabeledContent("Stable ID", value: host?.id ?? "Unknown") }
                if let cpu = host?.metrics?.cpu {
                    Section("Processor") { LabeledContent("Model", value: cpu.name ?? "Unknown"); LabeledContent("Physical cores", value: cpu.physicalCores.map(String.init) ?? "Unknown"); LabeledContent("Logical CPUs", value: cpu.logicalCores.map(String.init) ?? "Unknown"); LabeledContent("Load", value: cpu.usagePercent.map { "\($0)%" } ?? "Unknown") }
                }
                if let memory = host?.metrics?.memory { Section(memory.kind == "unified" ? "Unified memory" : "RAM") { LabeledContent("Capacity", value: MetricFormat.exactBytes(memory.totalBytes)); LabeledContent("Used", value: MetricFormat.exactBytes(memory.usedBytes)) } }
                ForEach(host?.metrics?.gpus ?? []) { gpu in
                    Section(gpu.label) {
                        LabeledContent("Model", value: gpu.name ?? "Unknown"); LabeledContent("UUID", value: gpu.id)
                        LabeledContent("Load", value: gpu.usagePercent.map { "\($0)%" } ?? "Unknown")
                        if gpu.usesUnifiedMemory { Text("Uses the unified memory pool shown above.") } else { LabeledContent("VRAM capacity", value: MetricFormat.exactBytes(gpu.memoryTotalBytes)); LabeledContent("VRAM used", value: MetricFormat.exactBytes(gpu.memoryUsedBytes)) }
                        LabeledContent("Temperature", value: gpu.temperatureC.map { "\($0) °C" } ?? "Unknown"); LabeledContent("Power", value: gpu.powerW.map { "\($0) W" } ?? "Unknown")
                    }
                }
            }.font(.subheadline).navigationTitle("Hardware").toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}
