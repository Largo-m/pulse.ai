import Cocoa
import FlutterMacOS

final class SecurityScopedBookmarkPlugin: NSObject, FlutterPlugin {
  private var activeUrl: URL?

  static func register(with registrar: FlutterPluginRegistrar) {
    let channel = FlutterMethodChannel(
      name: "pulse_ai/security_scoped_bookmark",
      binaryMessenger: registrar.messenger
    )
    let instance = SecurityScopedBookmarkPlugin()
    registrar.addMethodCallDelegate(instance, channel: channel)
  }

  func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    switch call.method {
    case "createBookmark":
      createBookmark(call, result: result)
    case "startAccess":
      startAccess(call, result: result)
    case "stopAccess":
      stopAccess(result: result)
    default:
      result(FlutterMethodNotImplemented)
    }
  }

  private func createBookmark(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    guard let args = call.arguments as? [String: Any],
          let path = args["path"] as? String,
          !path.isEmpty
    else {
      result(
        FlutterError(
          code: "INVALID_ARGUMENT",
          message: "path is required",
          details: nil
        )
      )
      return
    }

    let url = URL(fileURLWithPath: path)
    let accessed = url.startAccessingSecurityScopedResource()
    defer {
      if accessed {
        url.stopAccessingSecurityScopedResource()
      }
    }

    do {
      let data = try url.bookmarkData(
        options: .withSecurityScope,
        includingResourceValuesForKeys: nil,
        relativeTo: nil
      )
      result(data.base64EncodedString())
    } catch {
      result(
        FlutterError(
          code: "BOOKMARK_CREATE_FAILED",
          message: error.localizedDescription,
          details: nil
        )
      )
    }
  }

  private func startAccess(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    guard let args = call.arguments as? [String: Any],
          let bookmarkBase64 = args["bookmark"] as? String,
          let data = Data(base64Encoded: bookmarkBase64)
    else {
      result(false)
      return
    }

    stopAccess(result: nil)

    var isStale = false
    do {
      let url = try URL(
        resolvingBookmarkData: data,
        options: .withSecurityScope,
        relativeTo: nil,
        bookmarkDataIsStale: &isStale
      )
      let accessed = url.startAccessingSecurityScopedResource()
      if accessed {
        activeUrl = url
      }
      result(accessed)
    } catch {
      result(false)
    }
  }

  private func stopAccess(result: FlutterResult?) {
    if let url = activeUrl {
      url.stopAccessingSecurityScopedResource()
      activeUrl = nil
    }
    result?(nil)
  }
}
