import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/cursor_connection_failure.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/cloud_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_agent_run_output.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/fakes/fake_workflow_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_completion_output_source.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/prd_run_connection_gate.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/append_stream_event_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/cancel_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/complete_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/fail_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/list_local_git_branches_use_case.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/start_prd_agent_run_use_case.dart';
import 'package:pulse_ai/features/orchestrator/presentation/bloc/prd_workflow_cubit.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_stream_line_ui_model.dart';
import 'package:pulse_ai/features/orchestrator/presentation/models/prd_workflow_phase_ui_status.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_buffer_policy.dart';
import 'package:pulse_ai/features/orchestrator/service/cursor_cloud_run_id_codec.dart';

import '../../domain/usecases/fake_cursor_prd_agent_service.dart';
import '../../domain/usecases/fake_local_git_branches_service.dart';
import '../../domain/usecases/fake_recent_projects_repository.dart';

final class _ControllablePrdAgentService implements CursorPrdAgentService {
  _ControllablePrdAgentService({
    required StreamController<PrdStreamEvent> stream,
  }) : _stream = stream;

  final StreamController<PrdStreamEvent> _stream;
  int startRunCallCount = 0;
  int cancelRunCallCount = 0;
  bool shouldFailStart = false;

  static final String cloudRunId = CursorCloudRunIdCodec.encode(
    agentId: 'bc-test',
    runId: 'run-test-001',
  );

  @override
  Future<Either<Failure, void>> preflight() async => right(null);

  @override
  Future<Either<Failure, void>> preflightCredential(String apiKey) async =>
      right(null);

  @override
  Future<PrdRunEntity> startRun(PrdRunContext context) async {
    startRunCallCount++;
    if (shouldFailStart) {
      throw const PrdRunOperationException(PrdRunFailure.cloudRunFailed());
    }
    return PrdRunEntity(
      id: 'run-local-id',
      workflowKey: '${context.projectId}::${context.slug}',
      cloudRunId: cloudRunId,
      status: PrdRunStatus.queued,
      startedAt: DateTime.utc(2026, 5, 21),
    );
  }

  @override
  Stream<PrdStreamEvent> watchRun(String cloudRunId) => _stream.stream;

  @override
  Future<void> cancelRun(String cloudRunId) async {
    cancelRunCallCount++;
  }

  @override
  Future<Either<Failure, CloudRunStatus>> fetchRunStatus(String cloudRunId) =>
      Future<Either<Failure, CloudRunStatus>>.value(
        left(const PrdRunFailure.cloudRunFailed()),
      );
}

final class _FixedCompletionOutputSource
    implements PrdRunCompletionOutputSource {
  const _FixedCompletionOutputSource(this.output);

  final PrdAgentRunOutput output;

  @override
  Future<PrdAgentRunOutput> resolve({
    required String runId,
    required String projectId,
    required String slug,
  }) async {
    return output;
  }
}

void main() {
  const String projectId = '550e8400-e29b-41d4-a716-446655440000';
  const String slug = 'payments-api';
  const String repoPath = '/Users/dev/repo';
  final DateTime fixedNow = DateTime.utc(2026, 5, 21, 15);

  late FakeWorkflowRepository workflowRepository;
  late FakePrdRunRepository prdRunRepository;
  late FakeArtifactRepository artifactRepository;
  late FakeRecentProjectsRepository projectsRepository;
  late FakeLocalGitBranchesService gitService;
  late StreamController<PrdStreamEvent> streamController;
  late _ControllablePrdAgentService agentService;
  late WorkflowEntity seededWorkflow;

  PrdWorkflowCubit buildCubit() {
    final StartPrdAgentRunUseCase startUseCase = StartPrdAgentRunUseCase(
      connectionGate: PreflightPrdRunConnectionGate(
        preflight: () async => right(null),
      ),
      buildPrdRunContextUseCase: BuildPrdRunContextUseCase(
        recentProjectsRepository: projectsRepository,
        listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
          service: gitService,
        ),
      ),
      prdRunRepository: prdRunRepository,
      workflowRepository: workflowRepository,
      cursorPrdAgentService: agentService,
      clock: () => fixedNow,
    );

    return PrdWorkflowCubit(
      startPrdAgentRunUseCase: startUseCase,
      appendStreamEventUseCase: AppendStreamEventUseCase(
        prdRunRepository: prdRunRepository,
        artifactRepository: artifactRepository,
      ),
      completePrdAgentRunUseCase: CompletePrdAgentRunUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        artifactRepository: artifactRepository,
        clock: () => fixedNow,
      ),
      cancelPrdAgentRunUseCase: CancelPrdAgentRunUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        cursorPrdAgentService: agentService,
        clock: () => fixedNow,
      ),
      failPrdAgentRunUseCase: FailPrdAgentRunUseCase(
        prdRunRepository: prdRunRepository,
        workflowRepository: workflowRepository,
        clock: () => fixedNow,
      ),
      cursorPrdAgentService: agentService,
      completionOutputSource: const _FixedCompletionOutputSource(
        FakeCursorPrdAgentServiceForLifecycle.sampleCompletionOutput,
      ),
    );
  }

  Future<void> seedWorkflow() async {
    await workflowRepository.create(
      projectId: projectId,
      slug: slug,
      branchName: 'main',
      directive: 'Build payments PRD',
    );
    projectsRepository.projects.add(
      LocalProjectEntity(
        id: projectId,
        canonicalPath: repoPath,
        displayName: 'Repo',
        lastAccessedAt: DateTime.utc(2026, 5, 20),
      ),
    );
    gitService.resultsByPath[repoPath] = const LocalGitBranchesResult(
      LocalGitBranchesOutcome.success,
      branches: <String>['main'],
      headBranchName: 'main',
    );
  }

  setUp(() async {
    workflowRepository = FakeWorkflowRepository();
    prdRunRepository = FakePrdRunRepository();
    artifactRepository = FakeArtifactRepository();
    projectsRepository = FakeRecentProjectsRepository();
    gitService = FakeLocalGitBranchesService();
    streamController = StreamController<PrdStreamEvent>();
    agentService = _ControllablePrdAgentService(stream: streamController)
      ..shouldFailStart = false;
    await seedWorkflow();
    seededWorkflow = (await workflowRepository.findBySlug(
      projectId: projectId,
      slug: slug,
    ))!;
  });

  tearDown(() {
    if (!streamController.isClosed) {
      unawaited(streamController.close());
    }
  });

  group('PrdWorkflowCubit', () {
    test('bindWorkflow maps workflow phase to UI status', () {
      final PrdWorkflowCubit cubit = buildCubit()
        ..bindWorkflow(
          workflow: seededWorkflow.copyWith(
            prdPhaseStatus: PrdPhaseStatus.pendingApproval,
          ),
          repoPath: repoPath,
        );

      expect(cubit.state.phaseStatus, PrdWorkflowPhaseUiStatus.pendingApproval);
    });

    test(
      'start run emits running and appends first stream line to state',
      () async {
        final PrdWorkflowCubit cubit = buildCubit()
          ..bindWorkflow(workflow: seededWorkflow, repoPath: repoPath);
        final Future<void> startFuture = cubit.startRun(
          directive: 'Build payments PRD',
        );
        await Future<void>.delayed(Duration.zero);
        streamController.add(
          PrdStreamEvent(
            runId: _ControllablePrdAgentService.cloudRunId,
            eventType: 'status',
            sequence: 1,
            timestamp: fixedNow,
            payloadSummary: 'status=RUNNING',
          ),
        );
        await startFuture;
        await Future<void>.delayed(Duration.zero);
        expect(cubit.state.phaseStatus, PrdWorkflowPhaseUiStatus.running);
        expect(cubit.state.isStarting, isFalse);
        expect(cubit.state.streamLines.length, 1);
        expect(cubit.state.streamLines.first.displayText, 'status=RUNNING');
        streamController.add(
          PrdStreamEvent(
            runId: _ControllablePrdAgentService.cloudRunId,
            eventType: 'status',
            sequence: 2,
            timestamp: fixedNow,
            payloadSummary: 'status=AWAITING_USER',
          ),
        );
        await Future<void>.delayed(Duration.zero);
        expect(cubit.state.requiresUserAction, isTrue);
        await cubit.close();
      },
    );

    test(
      'completed run emits pendingApproval and stops subscription',
      () async {
        final PrdWorkflowCubit cubit = buildCubit()
          ..bindWorkflow(workflow: seededWorkflow, repoPath: repoPath);
        final Future<void> startFuture = cubit.startRun(
          directive: 'Build payments PRD',
        );
        await Future<void>.delayed(Duration.zero);
        streamController
          ..add(
            PrdStreamEvent(
              runId: _ControllablePrdAgentService.cloudRunId,
              eventType: 'assistant',
              sequence: 1,
              timestamp: fixedNow,
              payloadSummary: 'Generating PRD draft.',
            ),
          )
          ..add(
            PrdStreamEvent(
              runId: _ControllablePrdAgentService.cloudRunId,
              eventType: 'done',
              sequence: 2,
              timestamp: fixedNow.add(const Duration(milliseconds: 1)),
            ),
          );
        await startFuture;
        await Future<void>.delayed(Duration.zero);
        final int lineCountAfterComplete = cubit.state.streamLines.length;
        streamController.add(
          PrdStreamEvent(
            runId: _ControllablePrdAgentService.cloudRunId,
            eventType: 'assistant',
            sequence: 99,
            timestamp: fixedNow,
            payloadSummary: 'Should be ignored',
          ),
        );
        await Future<void>.delayed(Duration.zero);
        expect(cubit.state.streamLines.length, lineCountAfterComplete);
        expect(
          cubit.state.phaseStatus,
          PrdWorkflowPhaseUiStatus.pendingApproval,
        );
        expect(cubit.state.activeRunId, isNull);
        await cubit.close();
      },
    );

    test(
      'cancel transitions to cancelled and clears active subscription',
      () async {
        final PrdWorkflowCubit cubit = buildCubit()
          ..bindWorkflow(workflow: seededWorkflow, repoPath: repoPath);
        final Future<void> startFuture = cubit.startRun(
          directive: 'Build payments PRD',
        );
        await Future<void>.delayed(Duration.zero);
        streamController.add(
          PrdStreamEvent(
            runId: _ControllablePrdAgentService.cloudRunId,
            eventType: 'status',
            sequence: 1,
            timestamp: fixedNow,
            payloadSummary: 'status=RUNNING',
          ),
        );
        await startFuture;
        await Future<void>.delayed(Duration.zero);
        await cubit.cancelActiveRun();
        streamController.add(
          PrdStreamEvent(
            runId: _ControllablePrdAgentService.cloudRunId,
            eventType: 'assistant',
            sequence: 2,
            timestamp: fixedNow,
            payloadSummary: 'late event',
          ),
        );
        await Future<void>.delayed(Duration.zero);
        expect(cubit.state.phaseStatus, PrdWorkflowPhaseUiStatus.cancelled);
        expect(cubit.state.activeRunId, isNull);
        expect(agentService.cancelRunCallCount, 1);
        await cubit.close();
      },
    );

    test(
      'failed run surfaces failure message key without secret substrings',
      () async {
        final PrdWorkflowCubit cubit = buildCubit()
          ..bindWorkflow(workflow: seededWorkflow, repoPath: repoPath);
        final Future<void> startFuture = cubit.startRun(
          directive: 'Build payments PRD',
        );
        await Future<void>.delayed(Duration.zero);
        streamController.add(
          PrdStreamEvent(
            runId: _ControllablePrdAgentService.cloudRunId,
            eventType: 'error',
            sequence: 1,
            timestamp: fixedNow,
            payloadSummary: 'error=upstream_error',
          ),
        );
        await startFuture;
        await Future<void>.delayed(Duration.zero);
        expect(cubit.state.phaseStatus, PrdWorkflowPhaseUiStatus.failed);
        expect(
          cubit.state.failureMessageKey,
          OrchestratorStrings.prdWorkflowRunFailedGeneric,
        );
        final String stateString = cubit.state.toString();
        expect(stateString, isNot(contains('sk-live-')));
        expect(stateString, isNot(contains('Bearer ')));
        await cubit.close();
      },
    );

    test('connection failure maps to cursor remediation key', () async {
      final PrdWorkflowCubit cubit = PrdWorkflowCubit(
        startPrdAgentRunUseCase: StartPrdAgentRunUseCase(
          connectionGate: PreflightPrdRunConnectionGate(
            preflight: () => Future<Either<Failure, void>>.value(
              left(const CursorConnectionFailure.missingCredential()),
            ),
          ),
          buildPrdRunContextUseCase: BuildPrdRunContextUseCase(
            recentProjectsRepository: projectsRepository,
            listLocalGitBranchesUseCase: ListLocalGitBranchesUseCase(
              service: gitService,
            ),
          ),
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          cursorPrdAgentService: agentService,
          clock: () => fixedNow,
        ),
        appendStreamEventUseCase: AppendStreamEventUseCase(
          prdRunRepository: prdRunRepository,
        ),
        completePrdAgentRunUseCase: CompletePrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          artifactRepository: artifactRepository,
          clock: () => fixedNow,
        ),
        cancelPrdAgentRunUseCase: CancelPrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          cursorPrdAgentService: agentService,
          clock: () => fixedNow,
        ),
        failPrdAgentRunUseCase: FailPrdAgentRunUseCase(
          prdRunRepository: prdRunRepository,
          workflowRepository: workflowRepository,
          clock: () => fixedNow,
        ),
        cursorPrdAgentService: agentService,
        completionOutputSource: const _FixedCompletionOutputSource(
          FakeCursorPrdAgentServiceForLifecycle.sampleCompletionOutput,
        ),
      );
      cubit.bindWorkflow(workflow: seededWorkflow, repoPath: repoPath);
      await cubit.startRun(directive: 'Build payments PRD');
      expect(
        cubit.state.failureMessageKey,
        OrchestratorStrings.cursorConnectionMissingCredentialRemediation,
      );
      await cubit.close();
    });

    test('caps in-memory stream lines at policy max', () {
      final List<PrdStreamLineUiModel> lines = <PrdStreamLineUiModel>[];
      for (
        int index = 0;
        index < PrdStreamBufferPolicy.maxInMemoryEvents + 5;
        index++
      ) {
        lines.add(
          PrdStreamLineUiModel(
            sequence: index,
            eventType: 'assistant',
            displayText: 'line-$index',
          ),
        );
      }
      expect(
        lines.length,
        greaterThan(PrdStreamBufferPolicy.maxInMemoryEvents),
      );
      final List<PrdStreamLineUiModel> capped = lines.sublist(
        lines.length - PrdStreamBufferPolicy.maxInMemoryEvents,
      );
      expect(capped.length, PrdStreamBufferPolicy.maxInMemoryEvents);
      expect(capped.first.displayText, contains('line-'));
    });
  });
}
