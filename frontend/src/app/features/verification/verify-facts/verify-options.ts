export type VerifyMethod = 'image' | 'source' | 'photocard';

export interface VerifyOption {
  key: VerifyMethod;
  title: string;
  icon: string;
  description: string;
}

export const VERIFY_OPTIONS: VerifyOption[] = [
  {
    key: 'image',
    title: 'News story against an image',
    icon: '▤',
    description:
      'Check if the news story matches the given image. First an initial ' +
      'result will be provided by model prediction. Then experts will review ' +
      'it and give the final result.',
  },
  {
    key: 'source',
    title: 'News story against claimed source',
    icon: '≡',
    description:
      'Check if the news story matches the original news from the claimed ' +
      'source. First an initial result will be provided by automatic ' +
      'evaluation. Then experts will review it and give the final result.',
  },
  {
    key: 'photocard',
    title: 'Photocard against claimed source',
    icon: '▧',
    description:
      'Check if the photocard matches the original news from the claimed ' +
      'source. First an initial result will be provided by automatic ' +
      'evaluation. Then experts will review it and give the final result.',
  },
];
