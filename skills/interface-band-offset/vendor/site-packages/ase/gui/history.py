# Right now the gui.update_history method is peppered around the code.
# It should probably work off the observers but right now I am not sure
# it can. Since draw() is called all over the place and it calls the
# change_atoms observer, this would lead to a lot of saved history
# states where nothing actually changed. If the proposed refactoring is
# done some day, registering update_history to the observers seems like
# the correct move.


class History:
    def __init__(self, images):
        self.max_entries = 20
        self.images = images
        self.initialize_history()

    def _is_at_end(self, frame):
        frame_history = self.history_per_image[frame]
        now = self.now_per_image[frame]
        return frame_history[now] is frame_history[-1]

    def _is_at_start(self, frame):
        frame_history = self.history_per_image[frame]
        now = self.now_per_image[frame]
        return frame_history[now] is frame_history[0]

    def append_image(self, image):
        self.history_per_image.append([image.copy()])
        self.now_per_image.append(-1)

    def cut_tail(self, frame: int, i: int):
        self.history_per_image[frame] = list(self.history_per_image[frame][:i])
        # If the 'now' index would point out of range, reset it (this could
        # be a problem if the index becomes positive somehow):
        if self.now_per_image[frame] >= len(self.history_per_image[frame]):
            self.now_per_image[frame] = -1

    def isolate_history(self, frame):
        """Takes the history of the given index and makes it the only one"""
        self.history_per_image = [self.history_per_image[frame]]
        self.now_per_image = [self.now_per_image[frame]]

    def initialize_history(self):
        """Copies the images' current states to the history and creates
        what's necessary to track changes"""
        # Will contain a list for each image containing its own linear history
        # (as copies of the Atoms objects [or anything mutable, really]):
        self.history_per_image = []
        # Will contain an index for each image pointing to the historic entry
        # which is 'active':
        self.now_per_image = []
        for img in self.images:
            self.history_per_image.append([img.copy()])
            self.now_per_image.append(-1)

    def insert_image(self, frame, image):
        self.history_per_image.insert(frame, [image.copy()])
        self.now_per_image.insert(frame, -1)

    def pop_image(self, frame):
        """Removes the entire history of an image"""
        self.history_per_image.pop(frame)
        self.now_per_image.pop(frame)

    def pop_history_item(self, frame, i):
        """Removes a point in an image's history"""
        len_history = len(self.history_per_image[frame])
        # The 'now' may shift when a history item is removed
        # -> let's take note:
        i_abs = i % len_history
        now = self.now_per_image[frame]
        if now < 0:
            now_abs = now % len_history
            if now_abs < i_abs:
                self.now_per_image[frame] = now + 1
        elif now > 0 and now > i_abs:
            self.now_per_image[frame] = now_abs - 1 - len_history
        else:
            self.now_per_image[frame] = -1
        # Finally, pop out the history:
        self.history_per_image[frame].pop(i)

    def redo_history(self, frame):
        if not self._is_at_end(frame):
            now = self.now_per_image[frame] + 1
            self.now_per_image[frame] = now
            self.images._images[frame] = self.history_per_image[frame][
                now
            ].copy()

    def undo_history(self, frame):
        if not self._is_at_start(frame):
            now = self.now_per_image[frame] - 1
            self.now_per_image[frame] = now
            self.images._images[frame] = self.history_per_image[frame][
                now
            ].copy()

    def update_history(self, frame):
        if len(self.history_per_image[frame]) >= self.max_entries:
            self.pop_history_item(frame, 0)
        if not self._is_at_end(frame):
            self.cut_tail(frame, self.now_per_image[frame] + 1)
        self.now_per_image[frame] = -1
        self.history_per_image[frame].append(self.images[frame].copy())
