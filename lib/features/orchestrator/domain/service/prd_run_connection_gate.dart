import 'package:fpdart/fpdart.dart';
import 'package:pulse_ai/core/error/failure.dart';

abstract interface class PrdRunConnectionGate {
  Future<Either<Failure, void>> ensureCanStart();
}

final class PreflightPrdRunConnectionGate implements PrdRunConnectionGate {
  PreflightPrdRunConnectionGate({
    required Future<Either<Failure, void>> Function() preflight,
  }) : _preflight = preflight;

  PreflightPrdRunConnectionGate.fromUseCase({
    required Future<Either<Failure, void>> Function() runPreflight,
  }) : _preflight = runPreflight;

  final Future<Either<Failure, void>> Function() _preflight;

  @override
  Future<Either<Failure, void>> ensureCanStart() => _preflight();
}
