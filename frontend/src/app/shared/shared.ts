import { Component, input } from '@angular/core';
import { Level } from '../core/models';

/** Shown on every result screen. One component, so it cannot be forgotten on one of them. */
@Component({
  selector: 'app-disclaimer',
  template: `<p class="disclaimer" role="note">Screening aid only, not a diagnosis.</p>`,
})
export class Disclaimer {}

@Component({
  selector: 'app-level',
  template: `<span class="pill" [class]="'pill lvl-' + level()">{{ level() }}</span>`,
})
export class LevelPill {
  level = input.required<Level>();
}
