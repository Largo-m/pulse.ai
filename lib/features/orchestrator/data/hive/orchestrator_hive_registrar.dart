import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/adapters/prd_approval_entity_adapter.dart';
import 'package:pulse_ai/features/orchestrator/data/adapters/prd_run_entity_adapter.dart';
import 'package:pulse_ai/features/orchestrator/data/adapters/stream_event_entity_adapter.dart';
import 'package:pulse_ai/features/orchestrator/data/adapters/workflow_entity_adapter.dart';
final class OrchestratorHiveRegistrar {
  static bool _registered = false;

  static void registerAdapters() {
    if (_registered) {
      return;
    }
    if (!Hive.isAdapterRegistered(WorkflowEntityAdapter().typeId)) {
      Hive.registerAdapter(WorkflowEntityAdapter());
    }
    if (!Hive.isAdapterRegistered(PrdRunEntityAdapter().typeId)) {
      Hive.registerAdapter(PrdRunEntityAdapter());
    }
    if (!Hive.isAdapterRegistered(PrdApprovalEntityAdapter().typeId)) {
      Hive.registerAdapter(PrdApprovalEntityAdapter());
    }
    if (!Hive.isAdapterRegistered(StreamEventEntityAdapter().typeId)) {
      Hive.registerAdapter(StreamEventEntityAdapter());
    }
    _registered = true;
  }

  static void resetForTesting() {
    _registered = false;
  }
}
