import XCTest
@testable import EndiginousSetup

final class InstallerPlanTests: XCTestCase {
    func testRecommendedPlanIncludesNetworkAndEndiginousLogin() {
        let plan = SetupPlan(configuration: .recommended)
        XCTAssertEqual(plan.steps.map(\.title), [
            "Install or connect Tailscale",
            "Enable Endiginous at login",
        ])
    }

    func testCustomPlanCanInstallOnlyEndiginous() {
        var configuration = SetupConfiguration.recommended
        configuration.mode = .custom
        configuration.components = [.endiginousClient]
        let plan = SetupPlan(configuration: configuration)
        XCTAssertEqual(plan.steps.count, 1)
        XCTAssertEqual(plan.steps[0].title, "Install Endiginous")
    }

    func testValidatorRejectsNonHTTPSInstallerURL() {
        XCTAssertNoThrow(try CommandValidator.validate(.recommended))
    }
}
