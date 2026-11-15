import Foundation
import SwiftUI
import Security
import WidgetKit

enum DeviceCredential {
    static func read(server: String) -> String? {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "cloud.blusa.bleet", kSecAttrAccount as String: server, kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
    static func save(_ token: String, server: String) throws {
        delete(server: server)
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "cloud.blusa.bleet", kSecAttrAccount as String: server, kSecValueData as String: Data(token.utf8), kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else { throw APIError.credentials }
    }
    static func delete(server: String) { SecItemDelete([kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: "cloud.blusa.bleet", kSecAttrAccount as String: server] as CFDictionary) }
}
enum APIError: LocalizedError {
    case server, authentication, unavailable, credentials
    var errorDescription: String? {
        switch self {
        case .server: "Enter an HTTPS server origin, without a path or credentials."
        case .authentication: "Enrollment or authorization failed. Check your code and access."
        case .unavailable: "The private gateway could not complete the request. Check your connection and try again."
        case .credentials: "Your device could not securely save its credential."
        }
    }
}
struct Pairing: Decodable, Identifiable {
    let id = UUID()
    let hostId: String
    let pairingUrl: String?
    let expiresAt: String?
    let qrPngBase64: String?
    enum CodingKeys: String, CodingKey { case hostId, pairingUrl, expiresAt, qrPngBase64 }
}
@MainActor final class APIClient {
    let session: URLSession
    init(configuration config: URLSessionConfiguration = .ephemeral) {
        config.timeoutIntervalForRequest = 20
        config.urlCache = nil
        config.httpCookieStorage = nil
        session = URLSession(configuration: config)
    }
    static func origin(_ value: String) throws -> URL {
        guard let parts = URLComponents(string: value.trimmingCharacters(in: .whitespacesAndNewlines)), parts.scheme == "https", parts.host != nil, parts.user == nil, parts.password == nil, parts.query == nil, parts.fragment == nil, parts.path.isEmpty || parts.path == "/", let url = parts.url else { throw APIError.server }
        return url
    }
    func request(server: String, path: String, method: String = "GET", body: [String: String]? = nil, authenticated: Bool = true) throws -> URLRequest {
        let origin = try Self.origin(server)
        var request = URLRequest(url: origin.appendingPathComponent(path))
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if authenticated {
            guard let token = DeviceCredential.read(server: server) else { throw APIError.authentication }
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body { request.httpBody = try JSONEncoder().encode(body); request.setValue("application/json", forHTTPHeaderField: "Content-Type") }
        return request
    }
    func data(_ request: URLRequest) async throws -> Data {
        do {
            let (data, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else { throw APIError.unavailable }
            guard (200..<300).contains(http.statusCode) else { throw http.statusCode == 401 || http.statusCode == 403 ? APIError.authentication : APIError.unavailable }
            return data
        } catch let error as APIError { throw error } catch { throw APIError.unavailable }
    }
    func enroll(server: String, code: String) async throws -> String {
        struct Response: Decodable { let token: String }
        let request = try request(server: server, path: "v1/enroll", method: "POST", body: ["code": code, "device_name": UIDevice.current.name], authenticated: false)
        let response = try JSONDecoder().decode(Response.self, from: await data(request))
        return response.token
    }
    func pair(server: String, host: String) async throws -> Pairing {
        let request = try request(server: server, path: "v1/t3/pair", method: "POST", body: ["host_id": host, "output": "both"])
        let decoder = JSONDecoder(); decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try decoder.decode(Pairing.self, from: await data(request))
    }
    func terminal(server: String, host: String, mode: String) throws -> URLSessionWebSocketTask {
        var request = try request(server: server, path: "v1/terminal")
        var parts = URLComponents(url: request.url!, resolvingAgainstBaseURL: false)!
        parts.scheme = "wss"
        parts.queryItems = [URLQueryItem(name: "host_id", value: host), URLQueryItem(name: "mode", value: mode)]
        request.url = parts.url
        return session.webSocketTask(with: request)
    }
}
@MainActor @Observable final class AppStore {
    var server = UserDefaults.standard.string(forKey: "server") ?? "https://bleet.zorak.blusa.cloud" {
        didSet { if server != oldValue { invalidateRequests() } }
    }
    var demo = false
    var snapshot: Snapshot?
    var selection = Selection()
    var error: String?
    var refreshing = false
    var settingsPresented = false
    var enrollmentCode = ""
    var desk = false
    var terminalHost: Host?
    var terminalMode = "monitor"
    var pairing: Pairing?
    var pairingBusy = false
    let client: APIClient
    private var polling: Task<Void, Never>?
    private var pairingRequest: Task<Pairing, Error>?
    private var generation = 0
    private var foregroundActive = false
    var host: Host? { snapshot?.hosts.first { $0.id == selection.hostID } }
    var gpu: GPU? { host?.gpu(id: selection.gpuID) }
    var authenticated: Bool { DeviceCredential.read(server: server) != nil }
    init(client: APIClient = APIClient()) {
        self.client = client
        snapshot = SnapshotCache.read()
        demo = UserDefaults(suiteName: SnapshotCache.group)?.bool(forKey: "snapshotIsDemo") ?? false
        if let snapshot { selection.reconcile(snapshot) }
    }
    func select(_ host: Host) { selection.hostID = host.id; selection.gpuID = host.metrics?.gpus?.first?.id; selection.coreID = nil }
    func active(_ active: Bool) {
        foregroundActive = active
        polling?.cancel(); polling = nil
        if !active { invalidateRequests(); return }
        polling = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                await self.refresh()
                try? await Task.sleep(for: .seconds(8))
            }
        }
    }
    func refresh() async {
        guard !demo, authenticated, !refreshing else { return }
        let version = generation, origin = server
        refreshing = true
        defer { if version == generation { refreshing = false } }
        do {
            let data = try await client.data(client.request(server: origin, path: "v1/snapshot"))
            guard version == generation, origin == server, !demo, !Task.isCancelled else { return }
            let incoming = try Snapshot.decode(data)
            snapshot = incoming; selection.reconcile(incoming); error = nil
            try SnapshotCache.write(data)
            UserDefaults(suiteName: SnapshotCache.group)?.set(false, forKey: "snapshotIsDemo")
            WidgetCenter.shared.reloadAllTimelines()
        } catch {
            guard version == generation, origin == server, !Task.isCancelled else { return }
            self.error = error is APIError ? error.localizedDescription : APIError.unavailable.localizedDescription
        }
    }
    func exploreDemo() {
        guard let url = Bundle.main.url(forResource: "snapshot.example", withExtension: "json"), let data = try? Data(contentsOf: url), let snapshot = try? Snapshot.decode(data) else { return }
        invalidateRequests()
        demo = true; self.snapshot = snapshot; selection.reconcile(snapshot); error = nil
        try? SnapshotCache.write(data)
        UserDefaults(suiteName: SnapshotCache.group)?.set(true, forKey: "snapshotIsDemo")
        WidgetCenter.shared.reloadAllTimelines(); settingsPresented = false
    }
    func enroll(code: String) async throws {
        guard foregroundActive else { throw CancellationError() }
        let origin = server
        let normalized = try APIClient.origin(server).absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        invalidateRequests()
        let version = generation
        let token = try await client.enroll(server: normalized, code: code)
        guard version == generation, origin == server, foregroundActive, !Task.isCancelled else { throw CancellationError() }
        try DeviceCredential.save(token, server: normalized)
        server = normalized; UserDefaults.standard.set(server, forKey: "server")
        demo = false; snapshot = nil; error = nil; settingsPresented = false
        await refresh()
    }
    func disconnect() {
        invalidateRequests()
        DeviceCredential.delete(server: server); demo = false; snapshot = nil; selection = Selection(); terminalHost = nil; pairing = nil
        UserDefaults(suiteName: SnapshotCache.group)?.set(false, forKey: "snapshotIsDemo")
        SnapshotCache.clear(); WidgetCenter.shared.reloadAllTimelines()
    }
    func pair() async {
        guard foregroundActive, !demo, !pairingBusy, let host else { return }
        let version = generation, origin = server
        let request = Task { try await client.pair(server: origin, host: host.id) }
        pairingRequest = request; pairingBusy = true
        defer { if version == generation { pairingBusy = false; pairingRequest = nil } }
        do {
            let response = try await request.value
            guard version == generation, origin == server, foregroundActive, !demo, self.host?.id == host.id, !Task.isCancelled else { return }
            pairing = response
        } catch {
            guard version == generation, origin == server, foregroundActive, !Task.isCancelled else { return }
            self.error = APIError.unavailable.localizedDescription
        }
    }
    private func invalidateRequests() {
        generation += 1
        pairingRequest?.cancel(); pairingRequest = nil
        pairing = nil; pairingBusy = false; refreshing = false; terminalHost = nil
    }
    func deepLink(_ url: URL) {
        guard url.scheme == "bleet" else { return }
        let components = URLComponents(url: url, resolvingAgainstBaseURL: false)
        let query = components?.queryItems ?? []
        if url.host == "enroll" {
            if let server = query.first(where: { $0.name == "server" })?.value { self.server = server }
            if let fragment = components?.fragment, let secret = URLComponents(string: "?" + fragment)?.queryItems?.first(where: { $0.name == "code" })?.value { enrollmentCode = secret }
            settingsPresented = true; return
        }
        if let host = query.first(where: { $0.name == "host" })?.value { selection.hostID = host }
        if let gpu = query.first(where: { $0.name == "gpu" })?.value { selection.gpuID = gpu }
        if let core = query.first(where: { $0.name == "core" })?.value { selection.coreID = core }
    }
}
