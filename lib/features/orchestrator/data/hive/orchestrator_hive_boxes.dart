import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_box_names.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_registrar.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';

final class OrchestratorHiveBoxes {
  OrchestratorHiveBoxes({
    required this.workflows,
    required this.prdRuns,
    required this.prdApprovals,
    required this.streamEvents,
  });

  final Box<WorkflowEntity> workflows;
  final Box<PrdRunEntity> prdRuns;
  final Box<PrdApprovalEntity> prdApprovals;
  final Box<StreamEventEntity> streamEvents;

  static Future<OrchestratorHiveBoxes> open() async {
    OrchestratorHiveRegistrar.registerAdapters();
    final Box<WorkflowEntity> workflows = await Hive.openBox<WorkflowEntity>(
      OrchestratorHiveBoxNames.workflows,
    );
    final Box<PrdRunEntity> prdRuns = await Hive.openBox<PrdRunEntity>(
      OrchestratorHiveBoxNames.prdRuns,
    );
    final Box<PrdApprovalEntity> prdApprovals =
        await Hive.openBox<PrdApprovalEntity>(
          OrchestratorHiveBoxNames.prdApprovals,
        );
    final Box<StreamEventEntity> streamEvents =
        await Hive.openBox<StreamEventEntity>(
          OrchestratorHiveBoxNames.streamEvents,
        );
    return OrchestratorHiveBoxes(
      workflows: workflows,
      prdRuns: prdRuns,
      prdApprovals: prdApprovals,
      streamEvents: streamEvents,
    );
  }
}
