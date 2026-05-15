import 'package:file_picker/file_picker.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/local_directory_picker_service.dart';

typedef DirectoryPathPicker = Future<String?> Function();

final class LocalDirectoryPickerServiceImpl
    implements LocalDirectoryPickerService {
  LocalDirectoryPickerServiceImpl({DirectoryPathPicker? pickDirectory})
    : _pickDirectory = pickDirectory ?? _defaultPickDirectory;

  final DirectoryPathPicker _pickDirectory;

  static Future<String?> _defaultPickDirectory() {
    return FilePicker.getDirectoryPath(lockParentWindow: true);
  }

  @override
  Future<DirectoryPickResult> pickDirectory() async {
    try {
      final String? path = await _pickDirectory();
      if (path == null) {
        return const DirectoryPickResult(DirectoryPickOutcome.cancelled);
      }

      return DirectoryPickResult(
        DirectoryPickOutcome.success,
        absolutePath: path,
      );
    } on Object catch (error) {
      return DirectoryPickResult(
        DirectoryPickOutcome.failure,
        failureMessage: error.toString(),
      );
    }
  }
}
