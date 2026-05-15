enum DirectoryPickOutcome { cancelled, success, failure }

final class DirectoryPickResult {
  const DirectoryPickResult(
    this.outcome, {
    this.absolutePath,
    this.failureMessage,
  });

  final DirectoryPickOutcome outcome;
  final String? absolutePath;
  final String? failureMessage;
}

abstract interface class LocalDirectoryPickerService {
  Future<DirectoryPickResult> pickDirectory();
}
