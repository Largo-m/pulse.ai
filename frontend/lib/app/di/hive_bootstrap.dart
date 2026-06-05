import 'package:hive_flutter/hive_flutter.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_registrar.dart';

final class HiveBootstrap {
  static bool _initialized = false;

  static Future<void> ensureInitialized() async {
    if (_initialized) {
      return;
    }
    await Hive.initFlutter();
    OrchestratorHiveRegistrar.registerAdapters();
    _initialized = true;
  }

  static void resetForTesting() {
    _initialized = false;
    OrchestratorHiveRegistrar.resetForTesting();
  }
}
