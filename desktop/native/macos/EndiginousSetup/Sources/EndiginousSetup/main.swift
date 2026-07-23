import SwiftUI

@main
struct EndiginousSetupApp: App {
    var body: some Scene {
        WindowGroup("Endiginous Setup") {
            InstallerView()
                .frame(minWidth: 720, minHeight: 560)
        }
        .windowResizability(.contentSize)
    }
}
