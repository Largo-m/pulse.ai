import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_status_extensions.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/stream_event_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/artifact_repository.dart';
import 'package:pulse_ai/features/orchestrator/domain/repositories/prd_run_repository.dart';

final class AppendStreamEventUseCase {
  AppendStreamEventUseCase({
    required PrdRunRepository prdRunRepository,
    ArtifactRepository? artifactRepository,
    bool archiveToJsonl = true,
  }) : _prdRunRepository = prdRunRepository,
       _artifactRepository = artifactRepository,
       _archiveToJsonl = archiveToJsonl;

  final PrdRunRepository _prdRunRepository;
  final ArtifactRepository? _artifactRepository;
  final bool _archiveToJsonl;

  Future<Either<Failure, StreamEventEntity>> call({
    required String runId,
    required String projectId,
    required String slug,
    required PrdStreamEvent event,
  }) async {
    final PrdRunEntity? run = await _prdRunRepository.findRunById(runId);
    if (run == null) {
      return left(const PrdRunFailure.cloudRunNotFound());
    }
    if (!run.status.acceptsStreamEvents) {
      return left(const PrdRunFailure.runNotActive());
    }

    final Either<Failure, StreamEventEntity> appendResult =
        await _prdRunRepository.appendStreamEvent(
          runId: runId,
          eventType: event.eventType,
          payloadSummary: event.payloadSummary ?? '',
          timestamp: event.timestamp,
        );
    if (appendResult.isLeft()) {
      return appendResult;
    }

    final ArtifactRepository? artifactRepository = _artifactRepository;
    if (_archiveToJsonl && artifactRepository != null) {
      final StreamEventEntity stored = appendResult.getRight().toNullable()!;
      final Either<Failure, void> archiveResult = await artifactRepository
          .appendStreamJsonl(
            projectId: projectId,
            slug: slug,
            runId: runId,
            event: stored,
          );
      if (archiveResult.isLeft()) {
        return left(archiveResult.getLeft().toNullable()!);
      }
    }

    return appendResult;
  }
}
