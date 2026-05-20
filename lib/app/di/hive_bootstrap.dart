import 'package:hive_flutter/hive_flutter.dart';

final class HiveBootstrap {
  static bool _initialized = false;

  static Future<void> ensureInitialized() async {
    if (_initialized) {
      return;
    }
    await Hive.initFlutter();
    _initialized = true;
  }

  static void resetForTesting() {
    _initialized = false;
  }
}
