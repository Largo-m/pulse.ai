import 'package:pulse_ai/features/orchestrator/domain/service/local_directory_picker_service.dart';

final class FakeLocalDirectoryPickerService
    implements LocalDirectoryPickerService {
  DirectoryPickResult nextResult = const DirectoryPickResult(
    DirectoryPickOutcome.cancelled,
  );

  int pickCallCount = 0;

  @override
  Future<DirectoryPickResult> pickDirectory() async {
    pickCallCount++;
    return nextResult;
  }
}
