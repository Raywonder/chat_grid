// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "EndiginousSetup",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "EndiginousSetup", targets: ["EndiginousSetup"]),
    ],
    targets: [
        .executableTarget(name: "EndiginousSetup"),
        .testTarget(name: "EndiginousSetupTests", dependencies: ["EndiginousSetup"]),
    ]
)
