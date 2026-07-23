import XCTest
@testable import EndiginousSetup

final class InstallerPlanTests: XCTestCase {
    func testRecommendedPlanIncludesNetworkOpenClawGatewayAndLaunchAgent() {
        let plan = SetupPlan(configuration: .recommended)
        XCTAssertEqual(plan.steps.map(\.title), [
            "Install or connect Tailscale",
            "Install and configure OpenClaw",
            "Register this Mac as a gateway device",
            "Enable the per-user gateway launch agent",
        ])
    }

    func testCustomPlanCanInstallOnlyOpenClaw() {
        var configuration = SetupConfiguration.recommended
        configuration.mode = .custom
        configuration.components = [.openClaw]
        let plan = SetupPlan(configuration: configuration)
        XCTAssertEqual(plan.steps.count, 1)
        XCTAssertEqual(plan.steps[0].title, "Install and configure OpenClaw")
    }

    func testValidatorRejectsNonHTTPSInstallerURL() {
        var configuration = SetupConfiguration.recommended
        configuration.openClawInstallerURL = "http://example.invalid/setup.sh"
        XCTAssertThrowsError(try CommandValidator.validate(configuration))
    }
}
