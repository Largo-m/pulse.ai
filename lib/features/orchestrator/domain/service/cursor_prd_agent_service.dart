import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';

abstract interface class CursorPrdAgentService {
  Future<Either<Failure, void>> preflight();

  Future<Either<Failure, void>> preflightCredential(String apiKey);

  Future<PrdRunEntity> startRun(PrdRunContext context);

  Stream<PrdStreamEvent> watchRun(String cloudRunId);

  Future<void> cancelRun(String cloudRunId);
}
