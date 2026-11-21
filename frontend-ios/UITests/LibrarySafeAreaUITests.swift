import XCTest
import UIKit

/// Compare the scrollable content with the launch bar, which stays in the system safe area.
@MainActor final class LibrarySafeAreaUITests: XCTestCase {
    func testLandscapeShelfAndTitleRespectBothSafeEdges() {
        continueAfterFailure = true
        let app = XCUIApplication()
        defer {
            app.terminate()
            XCUIDevice.shared.orientation = .portrait
        }
        for dark in [false, true] {
            XCUIDevice.shared.orientation = .portrait
            app.launchArguments = ["--screen", "library", "--samples",
                                   dark ? "--dark-appearance" : "--light-appearance"]
            app.launch()
            XCTAssertTrue(app.buttons["tile.orbit"].waitForExistence(timeout: 10))
            for orientation in [UIDeviceOrientation.landscapeLeft, .landscapeRight] {
                XCUIDevice.shared.orientation = orientation
                let settled = NSPredicate { _, _ in
                    let window = app.windows.firstMatch.frame
                    return window.width > window.height && app.buttons["state.action"].isHittable
                }
                XCTAssertEqual(XCTWaiter.wait(for: [XCTNSPredicateExpectation(predicate: settled, object: nil)], timeout: 5), .completed)
                let launch = app.buttons["state.action"]
                let hero = app.staticTexts["hero.title"]
                let tile = app.buttons["tile.orbit"]
                XCTAssertGreaterThanOrEqual(hero.frame.minX, launch.frame.minX - 1,
                    "The title must share the launch bar's safe leading margin")
                XCTAssertGreaterThanOrEqual(tile.frame.minX, launch.frame.minX - 1,
                    "The first game must stay clear of the display cutout")
                XCTAssertLessThanOrEqual(hero.frame.maxX, app.windows.firstMatch.frame.maxX - launch.frame.minX + 1)
                XCTAssertTrue(app.buttons["shellSettings.open"].isHittable)
                XCTAssertTrue(app.buttons["gamePackage.import"].isHittable)
                let capture = XCTAttachment(screenshot: app.screenshot())
                capture.name = "safe-area-\(dark ? "dark" : "light")-\(orientation == .landscapeLeft ? "left" : "right")"
                capture.lifetime = .keepAlways
                add(capture)
            }
            app.terminate()
        }
    }
}
