import Cocoa
import FlutterMacOS

class MainFlutterWindow: NSWindow {
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    let windowFrame = self.frame
    self.contentViewController = flutterViewController
    self.setFrame(windowFrame, display: true)

    RegisterGeneratedPlugins(registry: flutterViewController)
    SecurityScopedBookmarkPlugin.register(
      with: flutterViewController.registrar(forPlugin: "SecurityScopedBookmarkPlugin")
    )

    super.awakeFromNib()
  }
}
