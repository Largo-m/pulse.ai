import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/core/error/prd_run_failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_context.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_entity.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_run_request.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/cursor_prd_agent_service.dart';
import 'package:pulse_ai/features/orchestrator/domain/usecases/build_prd_run_context_use_case.dart';

final class StartPrdRunUseCase {
  StartPrdRunUseCase({
    required BuildPrdRunContextUseCase buildPrdRunContextUseCase,
    required CursorPrdAgentService cursorPrdAgentService,
  }) : _buildPrdRunContextUseCase = buildPrdRunContextUseCase,
       _cursorPrdAgentService = cursorPrdAgentService;

  final BuildPrdRunContextUseCase _buildPrdRunContextUseCase;
  final CursorPrdAgentService _cursorPrdAgentService;

  Future<PrdRunEntity> call(PrdRunRequest request) async {
    final Either<Failure, PrdRunContext> contextResult =
        await _buildPrdRunContextUseCase(request);
    final PrdRunContext context = contextResult.fold(
      (Failure failure) => throw PrdRunOperationException(failure),
      (PrdRunContext value) => value,
    );

    return _cursorPrdAgentService.startRun(context);
  }
}
