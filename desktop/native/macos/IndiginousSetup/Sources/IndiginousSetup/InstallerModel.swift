import Foundation

enum SetupMode: String, CaseIterable, Identifiable {
    case recommended
    case custom

    var id: String { rawValue }
    var title: String { rawValue.capitalized }
}

enum SetupComponent: String, CaseIterable, Identifiable {
    case tailscale
    case indiginousClient
    case startAtLogin

    var id: String { rawValue }

    var title: String {
        switch self {
        case .tailscale: return "Connect this Mac through Tailscale"
        case .indiginousClient: return "Install the Indiginous native client"
        case .startAtLogin: return "Start Indiginous when I sign in"
        }
    }

    var detail: String {
        switch self {
        case .tailscale: return "Uses the approved Headscale login flow. Existing enrollment is preserved."
        case .indiginousClient: return "Installs the native, non-WebView Indiginous app when an app bundle is supplied."
        case .startAtLogin: return "Starts Indiginous for this user; no system-wide login item is created."
        }
    }
}

struct SetupConfiguration: Equatable {
    var mode: SetupMode = .recommended
    var components: Set<SetupComponent> = Set(SetupComponent.recommended)
    var deviceName = Host.current().localizedName ?? "Indiginous Mac"
    var headscaleURL = "https://headscale.tappedin.fm"
    var installLocation = "/Applications/BlindSoftware/Indiginous.app"

    static var recommended: SetupConfiguration { SetupConfiguration() }
}

extension Set where Element == SetupComponent {
    static var recommended: Set<SetupComponent> {
        [.tailscale, .startAtLogin]
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
        if configuration.components.contains(.startAtLogin) {
            planned.append(SetupStep(
                title: "Enable Indiginous at login",
                command: ["open", configuration.installLocation],
                resourceURL: nil,
                requiresAdministrator: false
            ))
        }
        if configuration.components.contains(.indiginousClient) {
            planned.append(SetupStep(
                title: "Install Indiginous",
                command: ["open", configuration.installLocation],
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
        let plan = SetupPlan(configuration: configuration)
        guard !plan.steps.isEmpty else { throw CommandValidationError.emptyCommand }
        guard !plan.steps.flatMap(\.command).contains(where: { [";", "&&", "||", ">", "<", "`"].contains($0) }) else {
            throw CommandValidationError.shellOperatorNotAllowed
        }
    }
}
