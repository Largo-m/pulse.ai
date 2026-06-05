import 'package:pulse_ai/core/error/failure.dart';

enum ArtifactPersistenceFailureCode { invalidPathSegment, notFound, ioError }

final class ArtifactPersistenceFailure implements Failure {
  const ArtifactPersistenceFailure({required this.code, required this.message});

  const ArtifactPersistenceFailure.invalidPathSegment(String segment)
    : this(
        code: ArtifactPersistenceFailureCode.invalidPathSegment,
        message: 'Identificador de caminho inválido: $segment',
      );

  const ArtifactPersistenceFailure.notFound()
    : this(
        code: ArtifactPersistenceFailureCode.notFound,
        message: 'Artefato PRD não encontrado',
      );

  const ArtifactPersistenceFailure.ioError()
    : this(
        code: ArtifactPersistenceFailureCode.ioError,
        message: 'Falha ao persistir artefato',
      );

  final ArtifactPersistenceFailureCode code;
  @override
  final String message;
}
