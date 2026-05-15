import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/domain/entities/local_project_entity.dart';
import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_radii.dart';
import 'package:pulse_ai/shared/ui/mouse_hover_builder.dart';

final class RecentProjectListTile extends StatelessWidget {
  const RecentProjectListTile({
    super.key,
    required this.project,
    required this.isActive,
    required this.onSelected,
  });

  final LocalProjectEntity project;
  final bool isActive;
  final VoidCallback onSelected;

  @override
  Widget build(BuildContext context) {
    final TextTheme textTheme = Theme.of(context).textTheme;
    final String semanticsLabel = isActive
        ? '${OrchestratorStrings.recentProjectActiveSemantics}: '
              '${project.displayName}'
        : '${OrchestratorStrings.recentProjectSelectSemantics}: '
              '${project.displayName}';

    return Semantics(
      button: true,
      selected: isActive,
      label: semanticsLabel,
      child: Tooltip(
        message: OrchestratorStrings.recentProjectListTileTooltip,
        child: Focus(
          child: MouseHoverBuilder(
            builder: (BuildContext context, bool isHovered) {
              final Color borderColor = isActive
                  ? PulseColors.primary
                  : isHovered
                  ? PulseColors.outline
                  : Colors.transparent;
              final Color backgroundColor = isActive
                  ? PulseColors.surfaceContainerHigh
                  : isHovered
                  ? PulseColors.surfaceContainerLow
                  : Colors.transparent;

              return AnimatedContainer(
                duration: const Duration(
                  milliseconds: PulseDimensions.borderTransitionMs,
                ),
                curve: Curves.easeInOut,
                decoration: BoxDecoration(
                  color: backgroundColor,
                  borderRadius: BorderRadius.circular(PulseRadii.standbyChip),
                  border: Border(
                    left: BorderSide(
                      width: PulseDimensions.importSourceAccentBarWidth,
                      color: borderColor,
                    ),
                  ),
                ),
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    onTap: onSelected,
                    borderRadius: BorderRadius.circular(PulseRadii.standbyChip),
                    hoverColor: Colors.white.withValues(
                      alpha: PulseDimensions.inkHoverAlpha,
                    ),
                    child: Padding(
                      padding: PulseInsets.textButton,
                      child: Text(
                        project.displayName,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: (textTheme.bodyMedium ?? const TextStyle())
                            .copyWith(
                              color: isActive
                                  ? PulseColors.primary
                                  : PulseColors.onSurface,
                              fontWeight: isActive
                                  ? FontWeight.w600
                                  : FontWeight.w500,
                            ),
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
