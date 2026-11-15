#if !SWIFT_PACKAGE
import XCTest
@testable import Bleet

/// Delays only the HTTPS boundary; real decoding, Keychain, AppStore and shared
/// widget cache remain in use. All responses are synthetic, with no fleet access.
private final class DelayedGateway: URLProtocol, @unchecked Sendable {
    private static let lock = NSLock()
    nonisolated(unsafe) private static var heldPath = ""
    nonisolated(unsafe) private static var pending: DelayedGateway?
    nonisolated(unsafe) private static var started: XCTestExpectation?
    nonisolated(unsafe) private static var snapshot = Data()

    static func prepare(path: String, snapshot: Data) -> XCTestExpectation {
        let started = XCTestExpectation(description: "Gateway received \(path)")
        lock.withLock { heldPath = path; pending = nil; self.started = started; self.snapshot = snapshot }
        return started
    }
    override class func canInit(with request: URLRequest) -> Bool { request.url?.host == "bleet-tests.invalid" }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        let (started, data): (XCTestExpectation?, Data) = Self.lock.withLock {
            if request.url?.path == Self.heldPath { Self.pending = self; return (Self.started, Data()) }
            return (nil, Self.snapshot)
        }
        if let started { started.fulfill() }
        else if request.url?.path == "/v1/enroll" { complete(Data(#"{"token":"synthetic-test-credential","scopes":["read","t3:pair"]}"#.utf8)) }
        else { complete(data) }
    }
    override func stopLoading() {} // A queued response may arrive despite cancellation.
    static func respond(_ data: Data) {
        let request = lock.withLock { let request = pending; pending = nil; return request }
        request?.complete(data)
    }
    private func complete(_ data: Data) {
        client?.urlProtocol(self, didReceive: HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "application/json"])!, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: data)
        client?.urlProtocolDidFinishLoading(self)
    }
}

@MainActor final class SessionTests: XCTestCase {
    private func fixture() throws -> Data { try Data(contentsOf: Bundle(for: Self.self).url(forResource: "snapshot.example", withExtension: "json")!) }
    private func store(holding path: String) async throws -> (AppStore, XCTestExpectation) {
        let data = try fixture()
        let started = DelayedGateway.prepare(path: path, snapshot: data)
        let configuration = URLSessionConfiguration.ephemeral
        configuration.protocolClasses = [DelayedGateway.self]
        let client = APIClient(configuration: configuration)
        try DeviceCredential.save("synthetic-test-credential", server: "https://bleet-tests.invalid")
        let store = AppStore(client: client)
        store.server = "https://bleet-tests.invalid"; store.demo = false
        store.snapshot = try Snapshot.decode(data); store.selection = Selection(hostID: "ts:brak")
        return (store, started)
    }
    private var pairing: Data { Data(#"{"host_id":"ts:brak","pairing_url":"https://t3.bleet-tests.invalid/#synthetic-pairing","expires_at":"2026-11-15T05:00:00Z","qr_png_base64":null}"#.utf8) }
    private func lateSnapshot() throws -> Data {
        var value = try JSONSerialization.jsonObject(with: fixture()) as! [String: Any]
        var hosts = value["hosts"] as! [[String: Any]]
        hosts[0]["name"] = "LATE LIVE HOST"; value["hosts"] = hosts
        return try JSONSerialization.data(withJSONObject: value)
    }
    func testLatePairingCannotSurviveBackgroundAndReturn() async throws {
        let (store, started) = try await store(holding: "/v1/t3/pair")
        defer { store.active(false); store.disconnect(); store.client.session.invalidateAndCancel() }
        store.active(true)
        let request = Task { await store.pair() }
        await fulfillment(of: [started], timeout: 5)
        store.active(false); store.active(true)
        DelayedGateway.respond(pairing)
        await request.value
        XCTAssertNil(store.pairing)
        XCTAssertFalse(store.pairingBusy)
        XCTAssertNil(store.error)
    }
    func testLatePairingCannotSurviveDisconnect() async throws {
        let (store, started) = try await store(holding: "/v1/t3/pair")
        defer { store.active(false); store.disconnect(); store.client.session.invalidateAndCancel() }
        store.active(true)
        let request = Task { await store.pair() }
        await fulfillment(of: [started], timeout: 5)
        store.disconnect()
        DelayedGateway.respond(pairing)
        await request.value
        XCTAssertNil(store.pairing)
        XCTAssertFalse(store.pairingBusy)
        XCTAssertNil(store.error)
    }
    func testLateRefreshCannotRepopulateDisconnectedWidgetCache() async throws {
        let (store, started) = try await store(holding: "/v1/snapshot")
        defer { store.disconnect(); store.client.session.invalidateAndCancel() }
        let request = Task { await store.refresh() }
        await fulfillment(of: [started], timeout: 5)
        store.disconnect()
        DelayedGateway.respond(try lateSnapshot())
        await request.value
        XCTAssertNil(store.snapshot)
        XCTAssertNil(SnapshotCache.read())
        XCTAssertFalse(store.refreshing)
    }
    func testLateRefreshCannotReplaceDemoWithLiveReadings() async throws {
        let (store, started) = try await store(holding: "/v1/snapshot")
        defer { store.disconnect(); store.client.session.invalidateAndCancel() }
        let request = Task { await store.refresh() }
        await fulfillment(of: [started], timeout: 5)
        store.exploreDemo()
        DelayedGateway.respond(try lateSnapshot())
        await request.value
        XCTAssertTrue(store.demo)
        XCTAssertEqual(store.host?.name, "BRAK")
        XCTAssertEqual(SnapshotCache.read()?.hosts.first?.name, "BRAK")
        XCTAssertTrue(UserDefaults(suiteName: SnapshotCache.group)?.bool(forKey: "snapshotIsDemo") == true)
    }
    func testLateEnrollmentCannotReconnectAfterDisconnect() async throws {
        let (store, started) = try await store(holding: "/v1/enroll")
        defer { store.active(false); store.disconnect(); store.client.session.invalidateAndCancel() }
        store.active(true)
        let request = Task { do { try await store.enroll(code: "synthetic-enrollment"); return true } catch { return false } }
        await fulfillment(of: [started], timeout: 5)
        store.disconnect()
        DelayedGateway.respond(Data(#"{"token":"synthetic-late-credential","scopes":["read","t3:pair"]}"#.utf8))
        let enrolled = await request.value
        XCTAssertFalse(enrolled)
        XCTAssertFalse(store.authenticated)
        XCTAssertNil(store.snapshot)
        XCTAssertNil(SnapshotCache.read())
    }
}
#endif
