# This is a vendored version of
# https://github.com/carlosescri/DottedDict/
# as the original is unmaintained and was not compatible with Python 3.9.
#
# The MIT License (MIT)
#
# Copyright (c) 2014 Carlos Escribano Rey
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import collections
import json
import re
from abc import ABCMeta, abstractmethod

SPLIT_REGEX = r"(?<!\\)(\.)"


def is_dotted_key(key):
    """Returns True if the key has any not-escaped dot inside"""
    return len(re.findall(SPLIT_REGEX, key)) > 0


def split_key(key, max_keys=0):
    """Splits a key but allows dots in the key name if they're scaped properly.

    Args:
        key (str): The key to be splitted.
        max_keys (int): The maximum number of keys to be extracted. 0 means no
            limits.

    Returns:
        A list of keys
    """
    parts = [x for x in re.split(SPLIT_REGEX, key) if x != "."]
    result = []
    while len(parts) > 0:
        if max_keys > 0 and len(result) == max_keys:
            break
        result.append(parts.pop(0))

    if len(parts) > 0:
        result.append(".".join(parts))
    return result


class DottedCollection(metaclass=ABCMeta):
    """Abstract Base Class for DottedDict and DottedDict"""

    @classmethod
    def factory(cls, initial=None):
        """Returns a DottedDict or a DottedList based on the type of the
        initial value, that must be a dict or a list. In other case the same
        original value will be returned.
        """
        if isinstance(initial, list):
            return DottedList(initial)
        elif isinstance(initial, dict):
            return DottedDict(initial)
        else:
            return initial

    @classmethod
    def load_json(cls, json_value):
        """Returns a DottedCollection from a JSON string"""
        return cls.factory(json.loads(json_value))

    @classmethod
    def _factory_by_index(cls, dotted_key):
        """Returns the proper DottedCollection that best suits the next key in
        the dotted_key string. First guesses the next key and then analyzes it.
        If the next key is numeric then returns a DottedList. In other case a
        DottedDict is returned.
        """
        if not isinstance(dotted_key, str):
            next_key = str(dotted_key)
        elif not is_dotted_key(dotted_key):
            next_key = dotted_key
        else:
            next_key, tmp = split_key(dotted_key, 1)

        return DottedCollection.factory([] if next_key.isdigit() else {})

    def __init__(self, initial):
        """Base constructor. If there are nested dicts or lists they are
        transformed into DottedCollection instances.
        """
        if not isinstance(initial, list) and not isinstance(initial, dict):
            raise ValueError("initial value must be a list or a dict")

        self._validate_initial(initial)

        self.store = initial

        if isinstance(self.store, list):
            data = enumerate(self.store)
        else:
            data = self.store.items()

        for key, value in data:
            try:
                self.store[key] = DottedCollection.factory(value)
            except ValueError:
                pass

    def _validate_initial(self, initial):
        """Validates data so no unescaped dotted key is present."""
        if isinstance(initial, list):
            for item in initial:
                self._validate_initial(item)
        elif isinstance(initial, dict):
            for key, item in initial.items():
                if is_dotted_key(key):
                    raise ValueError("{} is not a valid key inside a DottedCollection!".format(key))
                self._validate_initial(item)

    def __len__(self):
        return len(self.store)

    def __iter__(self):
        return iter(self.store)

    def __repr__(self):
        return repr(self.store)

    def to_json(self):
        return json.dumps(self, cls=DottedJSONEncoder)

    @abstractmethod
    def __getitem__(self, name):
        pass

    @abstractmethod
    def __setitem__(self, name, value):
        pass

    @abstractmethod
    def __delitem__(self, name):
        pass

    @abstractmethod
    def to_python(self):
        pass


class DottedList(DottedCollection, collections.abc.MutableSequence):
    """A list with support for the dotted path syntax"""

    def __init__(self, initial=None):
        DottedCollection.__init__(self, [] if initial is None else list(initial))

    def __getitem__(self, index):
        if isinstance(index, slice):
            return self.store[index]

        if isinstance(index, int) or (isinstance(index, str) and index.isdigit()):
            return self.store[int(index)]

        elif isinstance(index, str) and is_dotted_key(index):
            my_index, alt_index = split_key(index, 1)
            target = self.store[int(my_index)]

            # required by the dotted path
            if not isinstance(target, DottedCollection):
                raise IndexError('cannot get "{}" in "{}" ({})'.format(alt_index, my_index, repr(target)))

            return target[alt_index]

        else:
            raise IndexError(f"cannot get {index} in {repr(self.store)}")

    def __setitem__(self, index, value):
        if isinstance(index, int) or (isinstance(index, str) and index.isdigit()):
            # If the index does not exist in the list but it's the same index
            # we would obtain by appending the value to the list we actually
            # append the value. (***)
            if int(index) not in self.store and int(index) == len(self.store):
                self.store.append(DottedCollection.factory(value))
            else:
                self.store[int(index)] = DottedCollection.factory(value)

        elif isinstance(index, str) and is_dotted_key(index):
            my_index, alt_index = split_key(index, 1)

            # (***)
            if int(my_index) not in self.store and int(my_index) == len(self.store):
                self.store.append(DottedCollection._factory_by_index(alt_index))

            if not isinstance(self[int(my_index)], DottedCollection):
                raise IndexError(
                    'cannot set "{}" in "{}" ({})'.format(alt_index, my_index, repr(self[int(my_index)]))
                )

            self[int(my_index)][alt_index] = DottedCollection.factory(value)

        else:
            raise IndexError("cannot use {} as index in {}".format(index, repr(self.store)))

    def __delitem__(self, index):
        if isinstance(index, int) or (isinstance(index, str) and index.isdigit()):
            del self.store[int(index)]

        elif isinstance(index, str) and is_dotted_key(index):
            my_index, alt_index = split_key(index, 1)
            target = self.store[int(my_index)]

            # required by the dotted path
            if not isinstance(target, DottedCollection):
                raise IndexError('cannot delete "{}" in "{}" ({})'.format(alt_index, my_index, repr(target)))

            del target[alt_index]

        else:
            raise IndexError("cannot delete {} in {}".format(index, repr(self.store)))

    def to_python(self):
        """Returns a plain python list and converts to plain python objects all
        this object's descendants.
        """
        result = list(self)

        for index, value in enumerate(result):
            if isinstance(value, DottedCollection):
                result[index] = value.to_python()

        return result

    def insert(self, index, value):
        self.store.insert(index, value)


class DottedDict(DottedCollection, collections.abc.MutableMapping):
    """A dict with support for the dotted path syntax"""

    def __init__(self, initial=None):
        DottedCollection.__init__(self, {} if initial is None else dict(initial))

    def __getitem__(self, k):
        key = self.__keytransform__(k)

        if not isinstance(k, str) or not is_dotted_key(key):
            return self.store[key]

        my_key, alt_key = split_key(key, 1)
        target = self.store[my_key]

        # required by the dotted path
        if not isinstance(target, DottedCollection):
            raise KeyError('cannot get "{}" in "{}" ({})'.format(alt_key, my_key, repr(target)))

        return target[alt_key]

    def __setitem__(self, k, value):
        key = self.__keytransform__(k)

        if not isinstance(k, str):
            raise KeyError("DottedDict keys must be str or unicode")
        elif not is_dotted_key(key):
            self.store[key] = DottedCollection.factory(value)
        else:
            my_key, alt_key = split_key(key, 1)

            if my_key not in self.store:
                self.store[my_key] = DottedCollection._factory_by_index(alt_key)

            self.store[my_key][alt_key] = value

    def __delitem__(self, k):
        key = self.__keytransform__(k)

        if not isinstance(k, str) or not is_dotted_key(key):
            del self.store[key]

        else:
            my_key, alt_key = split_key(key, 1)
            target = self.store[my_key]

            if not isinstance(target, DottedCollection):
                raise KeyError('cannot delete "{}" in "{}" ({})'.format(alt_key, my_key, repr(target)))

            del target[alt_key]

    def to_python(self):
        """Returns a plain python dict and converts to plain python objects all
        this object's descendants.
        """
        result = dict(self)

        for key, value in result.items():
            if isinstance(value, DottedCollection):
                result[key] = value.to_python()

        return result

    __getattr__ = __getitem__

    # self.store does not exist before __init__() initializes it

    def __setattr__(self, key, value):
        if key in self.__dict__ or key == "store":
            object.__setattr__(self, key, value)
        else:
            self.__setitem__(key, value)

    def __delattr__(self, key):
        if key in self.__dict__ or key == "store":
            object.__delattr__(self, key)
        else:
            self.__delitem__(key)

    def __contains__(self, k):
        key = self.__keytransform__(k)

        if not isinstance(k, str) or not is_dotted_key(key):
            return self.store.__contains__(key)

        my_key, alt_key = split_key(key, 1)
        target = self.store[my_key]

        if not isinstance(target, DottedCollection):
            return False

        return alt_key in target

    def __keytransform__(self, key):
        return key


#
# JSON stuff
#


class DottedJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, DottedCollection):
            return obj.store
        else:
            return json.JSONEncoder.default(obj)
