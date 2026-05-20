import 'package:hive/hive.dart';
import 'package:pulse_ai/features/orchestrator/data/hive/orchestrator_hive_type_ids.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/prd_phase_status.dart';
import 'package:pulse_ai/features/orchestrator/domain/entities/workflow_entity.dart';

final class WorkflowEntityAdapter extends TypeAdapter<WorkflowEntity> {
  @override
  int get typeId => OrchestratorHiveTypeIds.workflowEntity;

  @override
  WorkflowEntity read(BinaryReader reader) {
    final int fieldCount = reader.readByte();
    String projectId = '';
    String slug = '';
    String branchName = '';
    String? directive;
    PrdPhaseStatus prdPhaseStatus = PrdPhaseStatus.draft;
    DateTime createdAt = DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);

    for (int i = 0; i < fieldCount; i++) {
      switch (reader.readByte()) {
        case 0:
          projectId = reader.readString();
        case 1:
          slug = reader.readString();
        case 2:
          branchName = reader.readString();
        case 3:
          directive = reader.readBool() ? reader.readString() : null;
        case 4:
          prdPhaseStatus = PrdPhaseStatus.values[reader.readByte()];
        case 5:
          createdAt = DateTime.fromMillisecondsSinceEpoch(
            reader.readInt(),
            isUtc: true,
          );
      }
    }

    return WorkflowEntity(
      projectId: projectId,
      slug: slug,
      branchName: branchName,
      directive: directive,
      prdPhaseStatus: prdPhaseStatus,
      createdAt: createdAt,
    );
  }

  @override
  void write(BinaryWriter writer, WorkflowEntity obj) {
    writer
      ..writeByte(6)
      ..writeByte(0)
      ..writeString(obj.projectId)
      ..writeByte(1)
      ..writeString(obj.slug)
      ..writeByte(2)
      ..writeString(obj.branchName)
      ..writeByte(3)
      ..writeBool(obj.directive != null);
    if (obj.directive != null) {
      writer.writeString(obj.directive!);
    }
    writer
      ..writeByte(4)
      ..writeByte(obj.prdPhaseStatus.index)
      ..writeByte(5)
      ..writeInt(obj.createdAt.millisecondsSinceEpoch);
  }
}
