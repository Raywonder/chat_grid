import SwiftUI

@main
struct IndiginousSetupApp: App {
    var body: some Scene {
        WindowGroup("Indiginous Setup") {
            InstallerView()
                .frame(minWidth: 720, minHeight: 560)
        }
        .windowResizability(.contentSize)
    }
}
