import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status_extensions.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_session_snapshot.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/restore_prd_session_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/restore_prd_session_result.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';
import 'package:pulse_ai/features/orchestrator/presentation/prd_stream_event_mapper.dart';

final class RestoreLastFinalizedPrdSessionUseCase {
  RestoreLastFinalizedPrdSessionUseCase({
    required PrdRunRepository prdRunRepository,
    PrdStreamEventMapper? streamEventMapper,
  }) : _prdRunRepository = prdRunRepository,
       _streamEventMapper = streamEventMapper ?? const PrdStreamEventMapper();

  final PrdRunRepository _prdRunRepository;
  final PrdStreamEventMapper _streamEventMapper;

  Future<Either<Failure, RestorePrdSessionResult>> call(
    RestorePrdSessionRequest request,
  ) async {
    final Either<Failure, List<PrdRunEntity>> runsResult =
        await _prdRunRepository.listRunsForWorkflow(request.workflowKey);
    if (runsResult.isLeft()) {
      return left(runsResult.getLeft().toNullable()!);
    }

    final List<PrdRunEntity> runs = runsResult.getRight().toNullable()!;
    if (runs.isEmpty) {
      return right(
        const RestorePrdSessionResult(outcome: RestorePrdSessionOutcome.empty),
      );
    }

    final PrdRunEntity latestRun = runs.first;
    if (!latestRun.status.isTerminal) {
      return right(
        const RestorePrdSessionResult(
          outcome: RestorePrdSessionOutcome.inProgressOnly,
        ),
      );
    }

    final Either<Failure, List<StreamEventEntity>> eventsResult =
        await _prdRunRepository.listStreamEvents(latestRun.id);
    if (eventsResult.isLeft()) {
      return left(eventsResult.getLeft().toNullable()!);
    }

    final List<StreamEventEntity> events = eventsResult
        .getRight()
        .toNullable()!;
    final PrdStreamEventMapperResult mapped = _streamEventMapper
        .mapPersistedEvents(
          events: events,
          workflowDirective: request.workflowDirective,
          runFeedback: latestRun.feedback,
        );

    return right(
      RestorePrdSessionResult(
        outcome: RestorePrdSessionOutcome.restored,
        snapshot: PrdSessionSnapshot(
          runId: latestRun.id,
          runStatus: latestRun.status,
          terminalLines: mapped.terminalLines,
          conversationMessages: mapped.conversationMessages,
        ),
      ),
    );
  }
}
