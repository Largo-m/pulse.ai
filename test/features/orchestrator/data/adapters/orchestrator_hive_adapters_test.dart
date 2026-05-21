import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_registrar.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_approval_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';

void main() {
  group('Orchestrator Hive adapters', () {
    late Directory tempDir;
    late Box<dynamic> box;

    setUpAll(() async {
      tempDir = await Directory.systemTemp.createTemp('pulse_adapter_test_');
      Hive.init(tempDir.path);
      OrchestratorHiveRegistrar.registerAdapters();
    });

    tearDownAll(() async {
      await box.close();
      await Hive.close();
      if (tempDir.existsSync()) {
        tempDir.deleteSync(recursive: true);
      }
    });

    setUp(() async {
      box = await Hive.openBox<dynamic>('adapter_roundtrip');
    });

    tearDown(() async {
      await box.clear();
      await box.close();
    });

    test('WorkflowEntityAdapter round-trips entity fields', () async {
      final WorkflowEntity original = WorkflowEntity(
        projectId: '550e8400-e29b-41d4-a716-446655440000',
        slug: 'payments-api',
        branchName: 'main',
        directive: 'directive',
        prdPhaseStatus: PrdPhaseStatus.pendingApproval,
        createdAt: DateTime.utc(2026, 5, 20, 9),
      );

      await box.put('workflow', original);
      final WorkflowEntity? decoded = box.get('workflow') as WorkflowEntity?;
      expect(decoded, original);
    });

    test('PrdRunEntityAdapter round-trips entity fields', () async {
      final PrdRunEntity original = PrdRunEntity(
        id: 'run-1',
        workflowKey: 'project::slug',
        cloudRunId: 'cloud-1',
        status: PrdRunStatus.running,
        supersedesRunId: 'run-0',
        feedback: 'revise scope',
        startedAt: DateTime.utc(2026, 5, 20, 10),
        endedAt: DateTime.utc(2026, 5, 20, 11),
      );

      await box.put('run', original);
      final PrdRunEntity? decoded = box.get('run') as PrdRunEntity?;
      expect(decoded, original);
    });

    test('PrdApprovalEntityAdapter round-trips entity fields', () async {
      final PrdApprovalEntity original = PrdApprovalEntity(
        workflowKey: 'project::slug',
        status: PrdApprovalStatus.approved,
        approvedAt: DateTime.utc(2026, 5, 20, 12),
        lastEditedAt: DateTime.utc(2026, 5, 20, 11),
        sourceRunId: 'run-1',
      );

      await box.put('approval', original);
      final PrdApprovalEntity? decoded =
          box.get('approval') as PrdApprovalEntity?;
      expect(decoded, original);
    });

    test('StreamEventEntityAdapter round-trips entity fields', () async {
      final StreamEventEntity original = StreamEventEntity(
        runId: 'run-1',
        sequence: 3,
        eventType: 'delta',
        payloadSummary: 'chunk',
        timestamp: DateTime.utc(2026, 5, 20, 10, 30),
      );

      await box.put('event', original);
      final StreamEventEntity? decoded = box.get('event') as StreamEventEntity?;
      expect(decoded, original);
    });
  });
}
