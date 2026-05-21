import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';

abstract interface class WorkflowRepository {
  Future<Either<Failure, WorkflowEntity>> create({
    required String projectId,
    required String slug,
    required String branchName,
    String? directive,
  });

  Future<Either<Failure, List<WorkflowEntity>>> listByProject(String projectId);

  Future<WorkflowEntity?> findBySlug({
    required String projectId,
    required String slug,
  });
}
