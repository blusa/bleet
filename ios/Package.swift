// swift-tools-version: 6.0
import PackageDescription
let package = Package(name: "BleetModels", platforms: [.macOS(.v14)], products: [.library(name: "BleetModels", targets: ["BleetModels"])], targets: [.target(name: "BleetModels", path: "Shared"), .testTarget(name: "BleetModelsTests", dependencies: ["BleetModels"], path: "Tests", resources: [.copy("snapshot.example.json")])])
