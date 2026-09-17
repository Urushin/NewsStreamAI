# Apple client

SwiftUI package: `ios/NewsStreamApp/Package.swift`; deployment targets iOS 17 and macOS 14. Search symbols/files before opening broad Swift trees.

The client can still use legacy endpoints; verify the actual call site before changing backend contracts. V2 migration is intentionally incomplete per `docs/v2_reconciliation.md`.

Focused validation: `swift test --package-path ios/NewsStreamApp`. Use Xcode or `launch_simulator.sh` only when UI/runtime verification is required.
