import Foundation

enum SetupMode: String, CaseIterable, Identifiable {
    case recommended
    case custom

    var id: String { rawValue }
    var title: String { rawValue.capitalized }
}

enum SetupComponent: String, CaseIterable, Identifiable {
    case tailscale
    case openClaw
    case gatewayDevice
    case endiginousClient
    case startAtLogin

    var id: String { rawValue }

    var title: String {
        switch self {
        case .tailscale: return "Connect this Mac through Tailscale"
        case .openClaw: return "Install and configure OpenClaw"
        case .gatewayDevice: return "Set this Mac up as an OpenClaw gateway device"
        case .endiginousClient: return "Install the Endiginous native client"
        case .startAtLogin: return "Start the gateway service when I sign in"
        }
    }

    var detail: String {
        switch self {
        case .tailscale: return "Uses the approved Headscale login flow. Existing enrollment is preserved."
        case .openClaw: return "Runs the approved token-free macOS OpenClaw node installer."
        case .gatewayDevice: return "Requests the permissions needed for this device to be approved by the gateway owner."
        case .endiginousClient: return "Installs the native, non-WebView Endiginous app when an app bundle is supplied."
        case .startAtLogin: return "Installs a per-user launch agent; no system-wide login item is created."
        }
    }
}

struct SetupConfiguration: Equatable {
    var mode: SetupMode = .recommended
    var components: Set<SetupComponent> = Set(SetupComponent.recommended)
    var deviceName = Host.current().localizedName ?? "OpenClaw Mac"
    var headscaleURL = "https://headscale.tappedin.fm"
    var openClawInstallerURL = "https://tappedin.fm/downloads/openclaw/openclaw-join-macos.sh"

    static var recommended: SetupConfiguration { SetupConfiguration() }
}

extension Set where Element == SetupComponent {
    static var recommended: Set<SetupComponent> {
        [.tailscale, .openClaw, .gatewayDevice, .startAtLogin]
    }
}

struct SetupStep: Identifiable, Equatable {
    let id = UUID()
    let title: String
    let command: [String]
    let resourceURL: String?
    let requiresAdministrator: Bool
}

struct SetupPlan: Equatable {
    let steps: [SetupStep]

    init(configuration: SetupConfiguration) {
        var planned: [SetupStep] = []
        if configuration.components.contains(.tailscale) {
            planned.append(SetupStep(
                title: "Install or connect Tailscale",
                command: ["tailscale", "up", "--login-server", configuration.headscaleURL],
                resourceURL: nil,
                requiresAdministrator: true
            ))
        }
        if configuration.components.contains(.openClaw) {
            planned.append(SetupStep(
                title: "Install and configure OpenClaw",
                command: ["bash", "-s", "--", "--display-name", configuration.deviceName],
                resourceURL: configuration.openClawInstallerURL,
                requiresAdministrator: true
            ))
        }
        if configuration.components.contains(.gatewayDevice) {
            planned.append(SetupStep(
                title: "Register this Mac as a gateway device",
                command: ["openclaw", "node", "status"],
                resourceURL: nil,
                requiresAdministrator: false
            ))
        }
        if configuration.components.contains(.startAtLogin) {
            planned.append(SetupStep(
                title: "Enable the per-user gateway launch agent",
                command: ["launchctl", "bootstrap", "gui/$UID", "com.tappedin.openclaw-gateway"],
                resourceURL: nil,
                requiresAdministrator: false
            ))
        }
        if configuration.components.contains(.endiginousClient) {
            planned.append(SetupStep(
                title: "Install Endiginous",
                command: ["open", "/Applications/Endiginous.app"],
                resourceURL: nil,
                requiresAdministrator: true
            ))
        }
        steps = planned
    }
}

enum CommandValidationError: Error, LocalizedError {
    case unsafeURL
    case emptyCommand
    case shellOperatorNotAllowed

    var errorDescription: String? {
        switch self {
        case .unsafeURL: return "Only HTTPS installer URLs are allowed."
        case .emptyCommand: return "The setup step did not contain a command."
        case .shellOperatorNotAllowed: return "Shell operators are not allowed in native setup commands."
        }
    }
}

enum CommandValidator {
    static func validate(_ configuration: SetupConfiguration) throws {
        guard let url = URL(string: configuration.openClawInstallerURL), url.scheme == "https", url.host != nil else {
            throw CommandValidationError.unsafeURL
        }
        let plan = SetupPlan(configuration: configuration)
        guard !plan.steps.isEmpty else { throw CommandValidationError.emptyCommand }
        guard !plan.steps.flatMap(\.command).contains(where: { [";", "&&", "||", ">", "<", "`"].contains($0) }) else {
            throw CommandValidationError.shellOperatorNotAllowed
        }
    }
}
