def random=java.util.concurrent.ThreadLocalRandom.current()
vars.put('voteValue',vars.get('venueId')==vars.get('candidate_1') || random.nextBoolean() ? 'like' : 'dislike')
