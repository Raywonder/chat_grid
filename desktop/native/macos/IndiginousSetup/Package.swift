// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "IndiginousSetup",
    platforms: [.macOS(.v13)],
    products: [
        .executable(name: "IndiginousSetup", targets: ["IndiginousSetup"]),
    ],
    targets: [
        .executableTarget(name: "IndiginousSetup"),
        .testTarget(name: "IndiginousSetupTests", dependencies: ["IndiginousSetup"]),
    ]
)
