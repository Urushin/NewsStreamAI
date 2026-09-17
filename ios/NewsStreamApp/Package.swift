// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "NewsStreamApp",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(
            name: "NewsStreamApp",
            targets: ["NewsStreamApp"]
        ),
    ],
    dependencies: [],
    targets: [
        .target(
            name: "NewsStreamApp",
            dependencies: [],
            path: "Sources/NewsStreamApp",
            resources: [
                .process("Assets"),
                .process("Assets.xcassets")
            ]
        ),
        .testTarget(
            name: "NewsStreamAppTests",
            dependencies: ["NewsStreamApp"],
            path: "Tests"
        ),
    ]
)
