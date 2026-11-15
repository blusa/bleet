import SwiftUI
import WidgetKit
import AppIntents

struct MachineEntity: AppEntity {
    static let typeDisplayRepresentation: TypeDisplayRepresentation = "Machine"
    static let defaultQuery = MachineQuery()
    let id: String
    let name: String
    var displayRepresentation: DisplayRepresentation { DisplayRepresentation(title: "\(name)") }
}
struct MachineQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [MachineEntity] { machines.filter { identifiers.contains($0.id) } }
    func suggestedEntities() async throws -> [MachineEntity] { machines }
    func defaultResult() async -> MachineEntity? { machines.first }
    var machines: [MachineEntity] { (SnapshotCache.read()?.hosts ?? []).map { MachineEntity(id: $0.id, name: $0.name) } }
}
struct GPUEntity: AppEntity {
    static let typeDisplayRepresentation: TypeDisplayRepresentation = "GPU"
    static let defaultQuery = GPUQuery()
    let id: String
    let name: String
    var displayRepresentation: DisplayRepresentation { DisplayRepresentation(title: "\(name)") }
}
struct GPUQuery: EntityQuery {
    @IntentParameterDependency<ResourceIntent>(\.$machine) private var intent
    func entities(for identifiers: [String]) async throws -> [GPUEntity] {
        // Restore persisted identities even after Machine changes; rendering
        // rejects an explicit GPU that does not belong to that machine.
        (SnapshotCache.read()?.hosts ?? []).flatMap { host in
            (host.metrics?.gpus ?? []).filter { identifiers.contains($0.id) }.map { GPUEntity(id: $0.id, name: "\(host.name) · \($0.label)") }
        }
    }
    func suggestedEntities() async throws -> [GPUEntity] { gpus }
    var gpus: [GPUEntity] {
        guard let host = SnapshotCache.read()?.host(id: intent?.machine.id) else { return [] }
        return (host.metrics?.gpus ?? []).map { GPUEntity(id: $0.id, name: "\(host.name) · \($0.label)") }
    }
}
struct ResourceIntent: WidgetConfigurationIntent {
    static let title: LocalizedStringResource = "Resource snapshot"
    static let description = IntentDescription("Choose a machine and GPU from the latest saved fleet snapshot.")
    @Parameter(title: "Machine") var machine: MachineEntity?
    @Parameter(title: "GPU") var gpu: GPUEntity?
}
struct ResourceEntry: TimelineEntry {
    let date: Date
    let snapshot: Snapshot?
    let configuration: ResourceIntent
    let demo: Bool
    var host: Host? { snapshot?.host(id: configuration.machine?.id) }
    var gpu: GPU? { host?.gpu(id: configuration.gpu?.id) }
}
struct ResourceProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> ResourceEntry { ResourceEntry(date: .now, snapshot: nil, configuration: ResourceIntent(), demo: false) }
    func snapshot(for configuration: ResourceIntent, in context: Context) async -> ResourceEntry { read(configuration) }
    func timeline(for configuration: ResourceIntent, in context: Context) async -> Timeline<ResourceEntry> {
        let current = read(configuration)
        let entries = (0..<6).map { offset in ResourceEntry(date: current.date.addingTimeInterval(Double(offset * 60)), snapshot: current.snapshot, configuration: configuration, demo: current.demo) }
        return Timeline(entries: entries, policy: .after(current.date.addingTimeInterval(15 * 60)))
    }
    private func read(_ configuration: ResourceIntent) -> ResourceEntry { ResourceEntry(date: .now, snapshot: SnapshotCache.read(), configuration: configuration, demo: UserDefaults(suiteName: SnapshotCache.group)?.bool(forKey: "snapshotIsDemo") ?? false) }
}
enum ResourceKind: String { case cpu = "CPU", gpu = "GPU", memory = "Memory" }
struct ResourceWidgetView: View {
    let entry: ResourceEntry
    let kind: ResourceKind
    @Environment(\.widgetFamily) private var family
    @Environment(\.widgetRenderingMode) private var renderingMode
    @Environment(\.colorScheme) private var colorScheme
    var accessory: Bool { family == .accessoryRectangular || family == .accessoryCircular }
    var body: some View {
        Group {
            if let host = entry.host {
                VStack(alignment: .leading, spacing: accessory ? 3 : 10) {
                    if family != .accessoryCircular { HStack { Text(host.name).font(.caption.weight(.semibold)); Spacer(); Text(kind.rawValue).font(.caption2).foregroundStyle(.secondary) } }
                    instrument(host)
                    if family != .accessoryCircular {
                        HStack(spacing: 4) {
                            if entry.demo { Text("Demo ·") }
                            else if Snapshot.isStale(host.metrics?.collectedAt, now: entry.date) { Text("Saved ·") }
                            if let date = Snapshot.date(host.metrics?.collectedAt) { Text(date, style: .time) } else { Text("No measurement") }
                        }.font(.system(size: accessory ? 9 : 10)).foregroundStyle(.secondary).lineLimit(1)
                    }
                }
            } else { VStack(alignment: .leading, spacing: 8) { Image(systemName: "square.grid.3x3.fill").foregroundStyle(BleetStyle.mint); Text("Open Bleet").font(.headline); if !accessory { Text("Save a fleet snapshot to see resources here.").font(.caption).foregroundStyle(.secondary) } } }
        }
        .environment(\.colorScheme, renderingMode == .fullColor && !accessory ? .dark : colorScheme)
        .containerBackground(BleetStyle.background, for: .widget)
        .widgetURL(link(host: entry.host?.id, gpu: kind == .gpu ? entry.gpu?.id : nil))
    }
    @ViewBuilder func instrument(_ host: Host) -> some View {
        switch kind {
        case .cpu:
            if family == .accessoryCircular { Gauge(value: (host.metrics?.cpu?.usagePercent ?? 0) / 100) { measurementLabel } currentValueLabel: { Text(MetricFormat.percent(host.metrics?.cpu?.usagePercent)).font(.caption2) }.gaugeStyle(.accessoryCircularCapacity) }
            else if let cores = host.metrics?.cpu?.cores, !cores.isEmpty {
                HStack(spacing: 12) {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 3), count: accessory ? 8 : 4), spacing: 3) {
                        ForEach(cores.prefix(accessory ? 16 : 32)) { core in Link(destination: link(host: host.id, core: core.id)) { RoundedRectangle(cornerRadius: 3).fill(renderingMode == .fullColor ? BleetStyle.heat(core.usagePercent) : .primary.opacity(0.2 + (core.usagePercent ?? 0) / 140)).aspectRatio(1.2, contentMode: .fit).overlay { if !accessory { Text(core.usagePercent.map { String(format: "%.0f", $0) } ?? "—").font(.system(size: 8, design: .monospaced)).foregroundStyle((core.usagePercent ?? 0) >= 30 ? .black : .white) } } }.accessibilityLabel("Core \(core.index ?? 0), \(MetricFormat.percent(core.usagePercent))") }
                    }.frame(maxWidth: accessory ? .infinity : 100)
                    if family == .systemMedium { VStack(alignment: .leading, spacing: 6) { Text(MetricFormat.percent(host.metrics?.cpu?.usagePercent)).font(.title.weight(.medium)); Text(host.metrics?.cpu?.name ?? "CPU").font(.caption).foregroundStyle(.secondary); Text("Per-core load").font(.caption2).foregroundStyle(.secondary) } }
                }
            } else { Text("Per-core load unavailable").font(.caption) }
        case .gpu:
            if family == .accessoryCircular { Gauge(value: (entry.gpu?.usagePercent ?? 0) / 100) { measurementLabel } currentValueLabel: { Text(MetricFormat.percent(entry.gpu?.usagePercent)).font(.caption2) }.gaugeStyle(.accessoryCircularCapacity) }
            else { HStack(spacing: 12) { if accessory { Text(MetricFormat.percent(entry.gpu?.usagePercent)).font(.title3.monospacedDigit()) } else { GPUGauge(usage: entry.gpu?.usagePercent) }; if family == .systemMedium || accessory { VStack(alignment: .leading, spacing: 6) { Text(entry.gpu?.name ?? "GPU unavailable").font(.caption); Text(entry.gpu?.usesUnifiedMemory == true ? "Unified memory" : MetricFormat.bytes(entry.gpu?.memoryTotalBytes) + " VRAM").font(.caption2).foregroundStyle(.secondary) } } } }
        case .memory:
            VStack(spacing: accessory ? 5 : 14) {
                widgetMemory(title: host.metrics?.memory?.kind == "unified" ? "Unified" : "RAM", used: host.metrics?.memory?.usedBytes, total: host.metrics?.memory?.totalBytes)
                if !accessory, let gpu = entry.gpu, !gpu.usesUnifiedMemory, host.metrics?.memory?.kind != "unified" { widgetMemory(title: "VRAM", used: gpu.memoryUsedBytes, total: gpu.memoryTotalBytes) }
            }
        }
    }
    func widgetMemory(title: String, used: Double?, total: Double?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 4) { Text(title).fontWeight(.medium); Spacer(minLength: 0); Text(used.flatMap { used in total.map { String(format: "%.0f/%.0f GiB", used / 1_073_741_824, $0 / 1_073_741_824) } } ?? "—").foregroundStyle(.secondary).minimumScaleFactor(0.7) }.font(.caption2).lineLimit(1)
            GeometryReader { geometry in Capsule().fill(.primary.opacity(0.12)).overlay(alignment: .leading) { if let fraction = MetricFormat.fraction(used: used, total: total) { Capsule().fill(BleetStyle.mint).frame(width: geometry.size.width * fraction) } } }.frame(height: 5)
        }.accessibilityElement(children: .combine)
    }
    var measurementLabel: some View {
        Group { if let date = Snapshot.date(entry.host?.metrics?.collectedAt) { Text(date, style: .time) } else { Text("Saved") } }.font(.system(size: 7)).accessibilityLabel("Snapshot measurement time")
    }
    func link(host: String?, gpu: String? = nil, core: String? = nil) -> URL {
        var parts = URLComponents(); parts.scheme = "bleet"; parts.host = "resource"
        parts.queryItems = [URLQueryItem(name: "host", value: host), URLQueryItem(name: "gpu", value: gpu), URLQueryItem(name: "core", value: core)].filter { $0.value != nil }
        return parts.url!
    }
}
struct CPUWidget: Widget {
    var body: some WidgetConfiguration { AppIntentConfiguration(kind: "BleetCPU", intent: ResourceIntent.self, provider: ResourceProvider()) { ResourceWidgetView(entry: $0, kind: .cpu) }.configurationDisplayName("CPU heatmap").description("Per-core load from your latest saved measurement.").supportedFamilies([.systemSmall, .systemMedium, .accessoryRectangular, .accessoryCircular]) }
}
struct GPUWidget: Widget {
    var body: some WidgetConfiguration { AppIntentConfiguration(kind: "BleetGPU", intent: ResourceIntent.self, provider: ResourceProvider()) { ResourceWidgetView(entry: $0, kind: .gpu) }.configurationDisplayName("GPU load").description("A saved GPU measurement, with its measurement time.").supportedFamilies([.systemSmall, .systemMedium, .accessoryRectangular, .accessoryCircular]) }
}
struct MemoryWidget: Widget {
    var body: some WidgetConfiguration { AppIntentConfiguration(kind: "BleetMemory", intent: ResourceIntent.self, provider: ResourceProvider()) { ResourceWidgetView(entry: $0, kind: .memory) }.configurationDisplayName("Memory snapshot").description("RAM and dedicated VRAM, without duplicating unified memory.").supportedFamilies([.systemSmall, .systemMedium, .accessoryRectangular]) }
}
@main struct BleetWidgetBundle: WidgetBundle { var body: some Widget { CPUWidget(); GPUWidget(); MemoryWidget() } }
