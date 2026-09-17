import XCTest
@testable import NewsStreamApp

final class NewsStreamAppTests: XCTestCase {
    func testAlertPayloadDecoding() throws {
        let json = """
        {
            "alert_id": "test-123",
            "cluster_id": "cluster-abc",
            "timestamp": "2026-08-31T20:00:00Z",
            "push_title": "Accord historique sur le climat",
            "bullet_points": ["Point 1", "Point 2"],
            "sources": [
                {"name": "Le Monde", "domain": "lemonde.fr", "url": "https://lemonde.fr/1", "tier": 1},
                {"name": "BBC", "domain": "bbc.com", "url": "https://bbc.com/1", "tier": 1}
            ],
            "velocity_score": 2.5,
            "relevance_score": 0.9,
            "hybrid_score": 0.95,
            "reliability_label": "FAIT_OBJECTIF_FIABLE",
            "category": "Politique"
        }
        """.data(using: .utf8)!
        
        let alert = try JSONDecoder().decode(AlertPayload.self, from: json)
        XCTAssertEqual(alert.push_title, "Accord historique sur le climat")
        XCTAssertEqual(alert.sources.count, 2)
        XCTAssertTrue(alert.isMultiSource)
    }
}
