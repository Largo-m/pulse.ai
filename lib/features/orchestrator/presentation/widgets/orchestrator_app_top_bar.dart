import 'package:flutter/material.dart';

import 'package:pulse_ai/features/orchestrator/presentation/orchestrator_strings.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_dimensions.dart';
import 'package:pulse_ai/shared/theme/tokens/pulse_insets.dart';

final class OrchestratorAppTopBar extends StatelessWidget {
  const OrchestratorAppTopBar({
    super.key,
    required this.onPlaceholder,
    this.isWorkspacesActive = false,
    this.onWorkspaces,
    this.onImportProject,
  });

  final VoidCallback onPlaceholder;
  final bool isWorkspacesActive;
  final VoidCallback? onWorkspaces;
  final VoidCallback? onImportProject;

  @override
  Widget build(BuildContext context) {
    final TextTheme tt = Theme.of(context).textTheme;
    return Material(
      color: PulseColors.surfaceContainerLowest,
      child: SizedBox(
        height: PulseDimensions.appTopBarHeight,
        child: DecoratedBox(
          decoration: const BoxDecoration(
            border: Border(
              bottom: BorderSide(color: PulseColors.outlineVariant),
            ),
          ),
          child: Padding(
            padding: PulseInsets.appTopBar,
            child: Row(
              children: [
                Text(
                  OrchestratorStrings.brandName,
                  style: tt.labelMedium?.copyWith(
                    color: PulseColors.primary,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Container(
                  width: PulseDimensions.brandDividerWidth,
                  height: PulseDimensions.brandDividerHeight,
                  margin: const EdgeInsets.symmetric(
                    horizontal: PulseDimensions.brandDividerHorizontalMargin,
                  ),
                  color: PulseColors.outlineVariant,
                ),
                TextButton(
                  onPressed: onWorkspaces ?? onPlaceholder,
                  style: TextButton.styleFrom(
                    foregroundColor: isWorkspacesActive
                        ? PulseColors.primary
                        : PulseColors.onSurfaceVariant,
                    padding: PulseInsets.textButton,
                    minimumSize: Size.zero,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                  child: DecoratedBox(
                    decoration: BoxDecoration(
                      border: isWorkspacesActive
                          ? const Border(
                              bottom: BorderSide(
                                color: PulseColors.primary,
                                width: 2,
                              ),
                            )
                          : null,
                    ),
                    child: Padding(
                      padding: EdgeInsets.only(
                        bottom: isWorkspacesActive
                            ? PulseDimensions.sectionGapSm
                            : 0,
                      ),
                      child: Text(
                        OrchestratorStrings.workspacesNav,
                        style: tt.labelLarge?.copyWith(
                          color: isWorkspacesActive
                              ? PulseColors.primary
                              : PulseColors.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ),
                ),
                const Spacer(),
                FilledButton(
                  onPressed: onImportProject ?? onPlaceholder,
                  style: FilledButton.styleFrom(
                    backgroundColor: PulseColors.primary,
                    foregroundColor: PulseColors.onPrimary,
                    padding: PulseInsets.primaryTopBarButton,
                    textStyle: tt.labelLarge,
                  ),
                  child: const Text(OrchestratorStrings.importProject),
                ),
                const SizedBox(width: PulseDimensions.afterImportButtonGap),
                IconButton(
                  onPressed: onPlaceholder,
                  icon: const Icon(
                    Icons.settings_outlined,
                    size: PulseDimensions.chromeIconSize,
                  ),
                  color: PulseColors.onSurfaceVariant,
                  style: IconButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
                IconButton(
                  onPressed: onPlaceholder,
                  icon: const Icon(
                    Icons.notifications_none_outlined,
                    size: PulseDimensions.chromeIconSize,
                  ),
                  color: PulseColors.onSurfaceVariant,
                  style: IconButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
                IconButton(
                  onPressed: onPlaceholder,
                  icon: const Icon(
                    Icons.account_circle_outlined,
                    size: PulseDimensions.chromeIconSize,
                  ),
                  color: PulseColors.onSurfaceVariant,
                  style: IconButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
