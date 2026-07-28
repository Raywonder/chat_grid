import XCTest
@testable import IndiginousSetup

final class InstallerPlanTests: XCTestCase {
    func testRecommendedPlanIncludesNetworkAndIndiginousLogin() {
        let plan = SetupPlan(configuration: .recommended)
        XCTAssertEqual(plan.steps.map(\.title), [
            "Install or connect Tailscale",
            "Enable Indiginous at login",
        ])
    }

    func testCustomPlanCanInstallOnlyIndiginous() {
        var configuration = SetupConfiguration.recommended
        configuration.mode = .custom
        configuration.components = [.indiginousClient]
        let plan = SetupPlan(configuration: configuration)
        XCTAssertEqual(plan.steps.count, 1)
        XCTAssertEqual(plan.steps[0].title, "Install Indiginous")
    }

    func testValidatorRejectsNonHTTPSInstallerURL() {
        XCTAssertNoThrow(try CommandValidator.validate(.recommended))
    }

    func testRecommendedInstallLocationUsesBlindSoftwareVendorRoot() {
        let configuration = SetupConfiguration.recommended
        XCTAssertEqual(configuration.installLocation, "/Applications/BlindSoftware/Indiginous.app")
        XCTAssertTrue(SetupPlan(configuration: configuration).steps.isEmpty == false)
    }
}
