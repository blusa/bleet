#if os(iOS)
import SwiftUI

enum BleetStyle {
    static let mint = Color(red: 0.55, green: 0.87, blue: 0.76)
    static let background = Color(red: 0.055, green: 0.065, blue: 0.075)
    static let panel = Color(red: 0.105, green: 0.12, blue: 0.13)
    static func heat(_ load: Double?) -> Color {
        guard let load else { return .gray.opacity(0.25) }
        switch load {
        case ..<10: return Color(red: 0.16, green: 0.23, blue: 0.20)
        case ..<30: return Color(red: 0.22, green: 0.40, blue: 0.33)
        case ..<60: return Color(red: 0.43, green: 0.69, blue: 0.57)
        case ..<85: return Color(red: 0.79, green: 0.67, blue: 0.42)
        default: return Color(red: 0.88, green: 0.54, blue: 0.36)
        }
    }
}
struct CPUHeatmap: View {
    let cores: [Core]
    var selected: String? = nil
    var showValues = true
    var select: ((String) -> Void)? = nil
    var body: some View {
        LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 5), count: cores.count > 24 ? 8 : 4), spacing: 5) {
            ForEach(cores) { core in
                Button { select?(core.id) } label: {
                    RoundedRectangle(cornerRadius: 5)
                        .fill(BleetStyle.heat(core.usagePercent))
                        .overlay { if selected == core.id { RoundedRectangle(cornerRadius: 5).stroke(.white, lineWidth: 2) } }
                        .overlay { if showValues { Text(core.usagePercent.map { String(format: "%.0f", $0) } ?? "—").font(.system(.caption2, design: .monospaced)).foregroundStyle((core.usagePercent ?? 0) >= 30 ? .black : .white) } }
                        .aspectRatio(1.1, contentMode: .fit)
                }
                .buttonStyle(.plain)
                .accessibilityLabel("Core \(core.index.map(String.init) ?? core.id), \(MetricFormat.percent(core.usagePercent))")
                .accessibilityAddTraits(selected == core.id ? .isSelected : [])
            }
        }
    }
}
struct GPUGauge: View {
    let usage: Double?
    var body: some View {
        ZStack {
            Circle().trim(from: 0, to: 0.75).stroke(.white.opacity(0.10), style: StrokeStyle(lineWidth: 9, lineCap: .round)).rotationEffect(.degrees(135))
            Circle().trim(from: 0, to: (min(100, max(0, usage ?? 0)) / 100) * 0.75).stroke(BleetStyle.mint, style: StrokeStyle(lineWidth: 9, lineCap: .round)).rotationEffect(.degrees(135))
            VStack(spacing: 2) {
                Text(MetricFormat.percent(usage)).font(.system(.title, design: .rounded, weight: .medium)).monospacedDigit().minimumScaleFactor(0.6)
                Text("GPU load").font(.caption2).foregroundStyle(.secondary)
            }
        }.padding(7).aspectRatio(1, contentMode: .fit)
            .accessibilityElement(children: .ignore).accessibilityLabel("GPU load \(MetricFormat.percent(usage))")
    }
}
struct MemoryBar: View {
    let title: String
    let used: Double?
    let total: Double?
    var body: some View {
        VStack(alignment: .leading, spacing: 9) {
            ViewThatFits(in: .horizontal) {
                HStack { Text(title).fontWeight(.medium); Spacer(); values }
                VStack(alignment: .leading, spacing: 4) { Text(title).fontWeight(.medium); values }
            }.font(.subheadline)
            GeometryReader { geometry in
                Capsule().fill(.white.opacity(0.1)).overlay(alignment: .leading) {
                    if let fraction = MetricFormat.fraction(used: used, total: total) { Capsule().fill(BleetStyle.mint).frame(width: geometry.size.width * fraction) }
                }
            }.frame(height: 6)
        }.accessibilityElement(children: .combine)
    }
    var values: some View { Text("\(MetricFormat.bytes(used)) / \(MetricFormat.bytes(total))").font(.caption).foregroundStyle(.secondary).monospacedDigit() }
}
#endif
