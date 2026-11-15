#if os(iOS)
import Foundation
public enum SnapshotCache {
    public static let group = "group.cloud.blusa.bleet"
    private static var file: URL? { FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: group)?.appendingPathComponent("snapshot.json") }
    public static func read() -> Snapshot? { guard let file, let data = try? Data(contentsOf: file) else { return nil }; return try? Snapshot.decode(data) }
    public static func write(_ data: Data) throws { guard let file else { return }; try data.write(to: file, options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication]) }
    public static func clear() { if let file { try? FileManager.default.removeItem(at: file) } }
}
#endif
