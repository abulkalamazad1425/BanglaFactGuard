import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './home.html',
  styleUrls: ['./home.scss']
})
export class HomeComponent {


  readonly verdicts = [
    { label: 'Source Confirmed', icon: '✓', cls: 'badge-true', desc: 'The claimed source actually published a matching story. Checked independently of content or date.' },
    { label: 'Source Not Found', icon: '?', cls: 'badge-not-found', desc: 'No matching article could be located on the claimed source in the available search results. This alone does not show that the claim is false.' },
    { label: 'Content Matched', icon: '✓', cls: 'badge-true', desc: 'Once the source is confirmed, the claimed content carries the same facts — paraphrase and reordering included.' },
    { label: 'Content Altered', icon: '◑', cls: 'badge-partial', desc: 'Material facts changed, or the claim contradicts what the source actually published.' },
    { label: 'Date Matched / Mismatched', icon: '📅', cls: 'badge-partial', desc: 'Whether the claimed publication date matches the source’s actual date — informational only, never a verdict on the content.' },
  ];


}
