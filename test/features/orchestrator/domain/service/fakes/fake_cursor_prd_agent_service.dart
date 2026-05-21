import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_stream_event.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';

final class FakeCursorPrdAgentService implements CursorPrdAgentService {
  Either<Failure, void>? nextPreflightResult;

  @override
  Future<Either<Failure, void>> preflight() async {
    return nextPreflightResult ?? right(null);
  }

  @override
  Future<PrdRunEntity> startRun(PrdRunRequest request) {
    throw UnimplementedError();
  }

  @override
  Stream<PrdStreamEvent> watchRun(String cloudRunId) {
    throw UnimplementedError();
  }

  @override
  Future<void> cancelRun(String cloudRunId) {
    throw UnimplementedError();
  }
}
