import { defineStorage } from '@aws-amplify/backend';

export const storage = defineStorage({
  name: 'photoProtection',
  access: (allow) => ({
    'experiencePhotoForUser/{entity_id}/*': [
      allow.entity('identity').to(['read', 'write', 'delete'])
    ],
  })
});
