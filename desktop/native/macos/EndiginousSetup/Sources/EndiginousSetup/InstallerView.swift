import SwiftUI

struct InstallerView: View {
    @State private var configuration = SetupConfiguration.recommended
    @State private var isRunning = false
    @State private var status = "Ready to configure this Mac."
    @State private var errorMessage: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            header
            modePicker
            components
            details
            Divider()
            footer
        }
        .padding(28)
        .alert("Setup could not start", isPresented: Binding(get: { errorMessage != nil }, set: { if !$0 { errorMessage = nil } })) {
            Button("OK", role: .cancel) { errorMessage = nil }
        } message: {
            Text(errorMessage ?? "Unknown setup error")
        }
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 6) {
            Label("Endiginous", systemImage: "network")
                .font(.largeTitle.bold())
            Text("Native macOS setup for OpenClaw gateway devices")
                .font(.title3)
            Text("This app uses the approved Tailscale/Headscale and OpenClaw configuration without embedding keys or making the world client web-based.")
                .foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }

    private var modePicker: some View {
        Picker("Setup mode", selection: $configuration.mode) {
            ForEach(SetupMode.allCases) { mode in
                Text(mode.title).tag(mode)
            }
        }
        .pickerStyle(.segmented)
        .onChange(of: configuration.mode) { _, mode in
            if mode == .recommended { configuration.components = .recommended }
        }
        .accessibilityHint("Recommended selects the normal OpenClaw gateway setup. Custom lets you choose individual components.")
    }

    private var components: some View {
        GroupBox("What will be installed") {
            VStack(alignment: .leading, spacing: 12) {
                ForEach(SetupComponent.allCases) { component in
                    Toggle(isOn: Binding(
                        get: { configuration.components.contains(component) },
                        set: { enabled in
                            if enabled { configuration.components.insert(component) }
                            else { configuration.components.remove(component) }
                        }
                    )) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(component.title)
                            Text(component.detail).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    .disabled(configuration.mode == .recommended)
                }
            }
            .padding(.top, 4)
        }
    }

    private var details: some View {
        GroupBox("Device details") {
            Form {
                TextField("Device name", text: $configuration.deviceName)
                    .textContentType(.name)
                TextField("Headscale login server", text: $configuration.headscaleURL)
                    .textContentType(.URL)
                TextField("OpenClaw installer URL", text: $configuration.openClawInstallerURL)
                    .textContentType(.URL)
            }
            .padding(.top, 4)
        }
    }

    private var footer: some View {
        HStack(alignment: .center) {
            Text(status)
                .font(.callout)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Setup status: \(status)")
            Spacer()
            Button("Configure this Mac") { startSetup() }
                .keyboardShortcut(.defaultAction)
                .disabled(isRunning || configuration.components.isEmpty)
                .accessibilityHint("Opens the required macOS authorization prompts and runs the selected setup steps.")
        }
    }

    private func startSetup() {
        do {
            try CommandValidator.validate(configuration)
            let plan = SetupPlan(configuration: configuration)
            isRunning = true
            status = "Ready to run \(plan.steps.count) setup step\(plan.steps.count == 1 ? "" : "s")."
            // Execution is intentionally separated from the UI scaffold. The next implementation
            // phase will connect this plan to a signed SMJobBless helper and receipt writer.
            status = "Setup plan created. Administrator approval is required before changes run."
            isRunning = false
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
