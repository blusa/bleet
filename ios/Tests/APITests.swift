#if !SWIFT_PACKAGE
import XCTest
@testable import Bleet

@MainActor final class APITests: XCTestCase {
    func testGatewayOriginRejectsInsecureOrCredentialBearingURLs() async throws {
        XCTAssertNoThrow(try APIClient.origin("https://bleet.zorak.blusa.cloud"))
        for origin in ["http://example.com", "https://user:secret@example.com", "https://example.com?token=secret", "https://example.com/v1", "https://example.com#secret"] {
            XCTAssertThrowsError(try APIClient.origin(origin))
        }
    }
    func testUnauthenticatedEnrollmentUsesJSONBodyOnly() async throws {
        let client = APIClient()
        let request = try client.request(server: "https://example.com", path: "v1/enroll", method: "POST", body: ["code": "one-time"], authenticated: false)
        XCTAssertEqual(request.url?.absoluteString, "https://example.com/v1/enroll")
        XCTAssertNil(request.value(forHTTPHeaderField: "Authorization"))
        XCTAssertEqual(request.httpMethod, "POST")
        XCTAssertEqual((try JSONSerialization.jsonObject(with: XCTUnwrap(request.httpBody)) as? [String: String])?["code"], "one-time")
    }
}
#endif
