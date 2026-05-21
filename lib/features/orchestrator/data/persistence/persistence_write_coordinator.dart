import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';

final class PersistenceWriteCoordinator {
  const PersistenceWriteCoordinator();

  Future<Either<Failure, T>> commitFilesystemFirst<T>({
    required Future<Either<Failure, void>> Function() filesystemCommit,
    required Future<Either<Failure, T>> Function() hiveCommit,
    required Future<void> Function() rollbackFilesystem,
  }) async {
    final Either<Failure, void> filesystemResult = await filesystemCommit();
    if (filesystemResult.isLeft()) {
      return left(filesystemResult.getLeft().toNullable()!);
    }

    final Either<Failure, T> hiveResult = await hiveCommit();
    if (hiveResult.isLeft()) {
      await rollbackFilesystem();
      return left(hiveResult.getLeft().toNullable()!);
    }

    return hiveResult;
  }
}
