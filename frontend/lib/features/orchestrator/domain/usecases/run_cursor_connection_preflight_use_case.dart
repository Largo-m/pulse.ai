import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';

final class RunCursorConnectionPreflightUseCase {
  RunCursorConnectionPreflightUseCase({
    required CursorPrdAgentService cursorPrdAgentService,
  }) : _cursorPrdAgentService = cursorPrdAgentService;

  final CursorPrdAgentService _cursorPrdAgentService;

  Future<Either<Failure, void>> call() {
    return _cursorPrdAgentService.preflight();
  }
}
