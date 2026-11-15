import Foundation

public struct Snapshot: Codable, Sendable {
    public var collectedAt: String?
    public var hosts: [Host]
    public var events: [SourceMessage]?
    public var errors: [SourceMessage]?
    public func host(id: String?) -> Host? {
        guard let id else { return hosts.first }
        return hosts.first { $0.id == id }
    }
    public static func decode(_ data: Data) throws -> Snapshot {
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Snapshot.self, from: data)
    }
    public static func date(_ string: String?) -> Date? {
        guard let string else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let value = formatter.date(from: string) { return value }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: string)
    }
    public static func isStale(_ timestamp: String?, now: Date = Date()) -> Bool {
        guard let date = date(timestamp) else { return true }
        return now.timeIntervalSince(date) > 30
    }
}
public struct Host: Codable, Identifiable, Sendable {
    public var id: String
    public var name: String
    public var address: String?
    public var source: String?
    public var status: String?
    public var sshOnline: Bool?
    public var networkOnline: Bool?
    public var isT3: Bool?
    public var t3Url: String?
    public var lastSeen: String?
    public var metricsError: String?
    public var capabilities: [String]?
    public var metrics: Metrics?
    public func gpu(id: String?) -> GPU? {
        guard let id else { return metrics?.gpus?.first }
        return metrics?.gpus?.first { $0.id == id }
    }
}
public struct Metrics: Codable, Sendable {
    public var collectedAt: String?
    public var platform: String?
    public var cpu: CPU?
    public var memory: Memory?
    public var gpus: [GPU]?
}
public struct CPU: Codable, Sendable {
    public var name: String?
    public var physicalCores: Int?
    public var logicalCores: Int?
    public var usagePercent: Double?
    public var cores: [Core]?
    public var topologyLabel: String { physicalCores == nil ? "logical cores" : "physical cores" }
}
public struct Core: Codable, Identifiable, Sendable {
    public var id: String
    public var index: Int?
    public var usagePercent: Double?
    public var logicalIds: [Int]?
    public var state: String?
}
public struct Memory: Codable, Sendable {
    public var totalBytes: Double?
    public var usedBytes: Double?
    public var kind: String?
}
public struct GPU: Codable, Identifiable, Sendable {
    public var id: String
    public var index: Int?
    public var name: String?
    public var usagePercent: Double?
    public var memoryTotalBytes: Double?
    public var memoryUsedBytes: Double?
    public var temperatureC: Double?
    public var powerW: Double?
    public var memoryKind: String?
    public var label: String { index.map { "GPU \($0)" } ?? "GPU" }
    public var usesUnifiedMemory: Bool { memoryKind == "unified" }
    public var dedicatedMemoryFraction: Double? { usesUnifiedMemory ? nil : MetricFormat.fraction(used: memoryUsedBytes, total: memoryTotalBytes) }
}
public struct SourceMessage: Codable, Sendable {
    public var source: String?
    public var message: String?
    public var timestamp: String?
    public var hostId: String?
    public var type: String?
}
public struct Selection: Sendable {
    public var hostID: String?
    public var gpuID: String?
    public var coreID: String?
    public init(hostID: String? = nil, gpuID: String? = nil, coreID: String? = nil) { self.hostID = hostID; self.gpuID = gpuID; self.coreID = coreID }
    public mutating func reconcile(_ snapshot: Snapshot) {
        // Keep identities through temporary empty snapshots and window changes.
        if hostID == nil { hostID = snapshot.hosts.first?.id }
        guard let host = snapshot.hosts.first(where: { $0.id == hostID }) else { return }
        if gpuID == nil { gpuID = host.metrics?.gpus?.first?.id }
    }
}
public enum MetricFormat {
    public static func percent(_ value: Double?) -> String { value.map { String(format: "%.0f%%", $0) } ?? "—" }
    public static func fraction(used: Double?, total: Double?) -> Double? {
        guard let used, let total, total > 0, used >= 0 else { return nil }
        return min(1, max(0, used / total))
    }
    public static func bytes(_ value: Double?) -> String {
        guard let value else { return "—" }
        return String(format: "%.1f GiB", value / 1_073_741_824)
    }
    public static func exactBytes(_ value: Double?) -> String {
        guard let value else { return "Unknown" }
        return value.formatted(.number.precision(.fractionLength(0))) + " bytes"
    }
}
public struct TerminalFrame: Codable, Sendable {
    public var type: String
    public var data: String?
    public var cols: Int?
    public var rows: Int?
    public var status: Int?
    public var message: String?
    public init(type: String, data: String? = nil, cols: Int? = nil, rows: Int? = nil) { self.type = type; self.data = data; self.cols = cols; self.rows = rows }
}
