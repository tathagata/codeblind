// swift-tools-version:5.5
import PackageDescription

let package = Package(
    name: "swift_tts",
    platforms: [
        .macOS(.v12),
    ],
    targets: [
        .executableTarget(
            name: "swift_tts",
            path: "Sources"
        ),
    ]
)
