import 'dart:io';

import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_box_names.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_boxes.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_registrar.dart';

final class OrchestratorHiveTestHelper {
  static Directory? _tempDir;

  static Future<void> setUpHive() async {
    _tempDir = await Directory.systemTemp.createTemp('pulse_hive_test_');
    Hive.init(_tempDir!.path);
    OrchestratorHiveRegistrar.resetForTesting();
    OrchestratorHiveRegistrar.registerAdapters();
  }

  static Future<OrchestratorHiveBoxes> openBoxes() {
    return OrchestratorHiveBoxes.open();
  }

  static Future<void> tearDownHive() async {
    if (Hive.isBoxOpen(OrchestratorHiveBoxNames.workflows)) {
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.workflows).clear();
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.workflows).close();
    }
    if (Hive.isBoxOpen(OrchestratorHiveBoxNames.prdRuns)) {
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.prdRuns).clear();
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.prdRuns).close();
    }
    if (Hive.isBoxOpen(OrchestratorHiveBoxNames.prdApprovals)) {
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.prdApprovals).clear();
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.prdApprovals).close();
    }
    if (Hive.isBoxOpen(OrchestratorHiveBoxNames.streamEvents)) {
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.streamEvents).clear();
      await Hive.box<dynamic>(OrchestratorHiveBoxNames.streamEvents).close();
    }
    await Hive.close();
    if (_tempDir != null && await _tempDir!.exists()) {
      await _tempDir!.delete(recursive: true);
      _tempDir = null;
    }
    OrchestratorHiveRegistrar.resetForTesting();
  }
}
