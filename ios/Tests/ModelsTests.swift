import XCTest
#if SWIFT_PACKAGE
@testable import BleetModels
#else
@testable import Bleet
#endif

final class ModelsTests: XCTestCase {
    var fixtureBundle: Bundle {
#if SWIFT_PACKAGE
        Bundle.module
#else
        Bundle(for: Self.self)
#endif
    }
    func fixture() throws -> Snapshot {
        try Snapshot.decode(Data(contentsOf: fixtureBundle.url(forResource: "snapshot.example", withExtension: "json")!))
    }
    func testContractDecodingPreservesZeroAndGPUIdentity() throws {
        let host = try XCTUnwrap(fixture().hosts.first)
        XCTAssertEqual(host.metrics?.cpu?.cores?.first?.usagePercent, 0)
        XCTAssertEqual(host.metrics?.gpus?.last?.id, "GPU-demo-1")
        XCTAssertEqual(host.metrics?.memory?.totalBytes, 137438953472)
    }
    func testUnknownValuesAreNotRenderedAsZero() {
        XCTAssertEqual(MetricFormat.percent(nil), "—")
        XCTAssertNil(MetricFormat.fraction(used: 0, total: 0))
        XCTAssertEqual(MetricFormat.fraction(used: 0, total: 100), 0)
    }
    func testFractionalAndWholeDatesAndStaleMeasurement() {
        XCTAssertNotNil(Snapshot.date("2026-11-15T02:00:00.123Z"))
        XCTAssertNotNil(Snapshot.date("2026-11-15T02:00:00Z"))
        XCTAssertTrue(Snapshot.isStale("2026-11-15T02:00:00Z", now: Date(timeIntervalSince1970: 1794708120)))
        XCTAssertTrue(Snapshot.isStale(nil))
    }
    func testSelectionSurvivesGPUReorderingAndMissingHost() throws {
        var snapshot = try fixture()
        snapshot.hosts[0].metrics?.gpus?.reverse()
        var selection = Selection(hostID: "ts:brak", gpuID: "GPU-demo-1", coreID: "0:5")
        selection.reconcile(snapshot)
        XCTAssertEqual(selection.gpuID, "GPU-demo-1")
        XCTAssertEqual(selection.coreID, "0:5")
        selection.reconcile(Snapshot(collectedAt: nil, hosts: [], events: nil, errors: nil))
        XCTAssertEqual(selection.hostID, "ts:brak")
    }
    func testExplicitResourceSelectionNeverSubstitutesAnotherMachineOrGPU() throws {
        var snapshot = try fixture()
        var dexter = snapshot.hosts[0]
        dexter.id = "ts:dexter"; dexter.name = "DEXTER"
        dexter.metrics?.gpus?[0].id = "GPU-dexter"
        snapshot.hosts.append(dexter)
        let brak = try XCTUnwrap(snapshot.host(id: "ts:brak"))
        XCTAssertNil(brak.gpu(id: "GPU-dexter"))
        XCTAssertNil(brak.gpu(id: "removed-gpu"))
        XCTAssertEqual(brak.gpu(id: nil)?.id, "GPU-demo-0")
        XCTAssertEqual(snapshot.host(id: "ts:dexter")?.gpu(id: "GPU-dexter")?.id, "GPU-dexter")
        XCTAssertNil(snapshot.host(id: "missing-host"))
        XCTAssertEqual(snapshot.host(id: nil)?.id, "ts:brak")
    }
    func testUnifiedMemoryIsNotCountedAsDedicatedVRAM() throws {
        let data = Data(#"{"collected_at":null,"hosts":[{"id":"m","name":"Mac","status":"online","metrics":{"memory":{"total_bytes":100,"used_bytes":50,"kind":"unified"},"gpus":[{"id":"apple","index":0,"memory_kind":"unified","memory_total_bytes":100,"memory_used_bytes":50}]}}]}"#.utf8)
        let host = try XCTUnwrap(Snapshot.decode(data).hosts.first)
        XCTAssertTrue(host.metrics?.gpus?.first?.usesUnifiedMemory == true)
        XCTAssertNil(host.metrics?.gpus?.first?.dedicatedMemoryFraction)
    }
    func testTerminalFramesKeepANSIAndResizeProtocol() throws {
        let frame = try JSONDecoder().decode(TerminalFrame.self, from: Data(#"{"type":"output","data":"\u001b[32mhello"}"#.utf8))
        XCTAssertEqual(frame.data, "\u{1b}[32mhello")
        let resize = try JSONSerialization.jsonObject(with: JSONEncoder().encode(TerminalFrame(type: "resize", cols: 100, rows: 30))) as! [String: Any]
        XCTAssertEqual(resize["cols"] as? Int, 100)
        XCTAssertNil(resize["data"])
    }
}
