""" 
Module contains some conviniences for integration Custom Cells, 
that based on IC-stitcher, into KLayout Library as PCells.
IC-stitcher module has to be installed and visible for KLayout,
use 'sys.path.append(<path_to_python_lib_with_stitcher>)' to achieve this

!!! Not usable outside the Klayout !!!
"""
# import flayout # A lot of function are taken from it, quite helpfull
from inspect import Parameter, signature, Signature
from typing import Callable, Optional, Type

from ic_stitcher.configurations import kdb
from ic_stitcher import CustomCell

# PCell class that creates the PCell from a class defenition
class PCellFactory(kdb.PCellDeclarationHelper):
    def __init__(self, subclass:Type[CustomCell]) -> None:
        """Create a PCell from a subclass of a CustomCell class."""
        super().__init__()
        self.subclass = subclass
        # Getting a signiture of __init__
        self.init_sig = self._extract_sig(subclass.__init__) or {}
        self.func_name = subclass.__name__
        params = self._pcell_parameters(self.init_sig, on_error="raise")
        self._param_keys = list(params.keys())
        self._param_values = []
        for name, param in params.items():
            # Add the parameter to the PCell
            self._param_values.append(
                self.param(
                    name=name,
                    value_type=_klayout_type(param),
                    description=name.replace("_", " "),
                    default=param.default,
                )
            )

    def produce_impl(self):
        """Produce the PCell."""
        params = dict(zip(self._param_keys, self._param_values))
        subclass_obj = self.subclass(**params)
        # Add the cell to the layout
        internal_cell:kdb.Cell = self.cell # Typing hook
        internal_cell.copy_tree(subclass_obj.layout.kdb_cell)
        internal_cell.name = params[subclass_obj.name]

    def _pcell_parameters(self, sig: Signature, on_error="ignore"):
        """Get the parameters of a function."""
        # NOTE: There could be a better way to do this, than use __signature__.
        new_params = {}

        if len(sig.parameters) == 0:
            return new_params

        new_params = {'cell_name': Parameter('cell_name', kind=Parameter.KEYWORD_ONLY, default=self.func_name, annotation=str)}
        params = sig.parameters
        on_error = _validate_on_error(on_error)
        for name, param in params.items():
            try:
                new_params[name] = _validate_parameter(name, param)
            except ValueError:
                if on_error == "raise":
                    raise
        return new_params

    def _extract_sig(self, component:Callable):
        """Extract the signature of a function."""
        sig = signature(component)
        ignore_params = []
        params = sig.parameters

        for name, param in params.items():
            try:
                _validate_parameter(name, param)
            except:
                # Ignore parameters that are not accepted by KLayout
                ignore_params.append(name)

        ignore_params.append('cross_section')

        sig_new = Signature(
            [param for name, param in params.items() if name not in ignore_params]
        ) or {}
        return sig_new

def all_subclasses(cls):
    return set(cls.__subclasses__()).union(
        [s for c in cls.__subclasses__() for s in all_subclasses(c)])

MYLIB = kdb.Library()
def register_pcell_lib(libname:str, description:str = "IC-stitcher based library", subclasses = []):
    MYLIB.description = description
    if not subclasses:
        subclasses:set[Type[CustomCell]] = all_subclasses(CustomCell)
    for subcls in subclasses:
        MYLIB.layout().register_pcell(subcls.__name__, PCellFactory(subcls))
    MYLIB.register(libname)
    
# Klayout PCell type -> Python type Mapper
def _klayout_type(param: Parameter):
    type_map = {
        kdb.PCellDeclarationHelper.TypeInt: kdb.PCellDeclarationHelper.TypeInt,
        "TypeInt": kdb.PCellDeclarationHelper.TypeInt,
        "int": kdb.PCellDeclarationHelper.TypeInt,
        int: kdb.PCellDeclarationHelper.TypeInt,
        Optional[int]: kdb.PCellDeclarationHelper.TypeInt,
        kdb.PCellDeclarationHelper.TypeDouble: kdb.PCellDeclarationHelper.TypeDouble,
        "TypeDouble": kdb.PCellDeclarationHelper.TypeDouble,
        "float": kdb.PCellDeclarationHelper.TypeDouble,
        float: kdb.PCellDeclarationHelper.TypeDouble,
        Optional[float]: kdb.PCellDeclarationHelper.TypeDouble,
        kdb.PCellDeclarationHelper.TypeString: kdb.PCellDeclarationHelper.TypeString,
        "TypeString": kdb.PCellDeclarationHelper.TypeString,
        "str": kdb.PCellDeclarationHelper.TypeString,
        str: kdb.PCellDeclarationHelper.TypeString,
        Optional[str]: kdb.PCellDeclarationHelper.TypeString,
        kdb.PCellDeclarationHelper.TypeBoolean: kdb.PCellDeclarationHelper.TypeBoolean,
        "TypeBoolean": kdb.PCellDeclarationHelper.TypeBoolean,
        "bool": kdb.PCellDeclarationHelper.TypeBoolean,
        bool: kdb.PCellDeclarationHelper.TypeBoolean,
        Optional[bool]: kdb.PCellDeclarationHelper.TypeBoolean,
        kdb.PCellDeclarationHelper.TypeLayer: kdb.PCellDeclarationHelper.TypeLayer,
        "TypeLayer": kdb.PCellDeclarationHelper.TypeLayer,
        "LayerInfo": kdb.PCellDeclarationHelper.TypeLayer,
        kdb.LayerInfo: kdb.PCellDeclarationHelper.TypeLayer,
        kdb.PCellDeclarationHelper.TypeShape: kdb.PCellDeclarationHelper.TypeShape,
        "TypeShape": kdb.PCellDeclarationHelper.TypeShape,
        "Shape": kdb.PCellDeclarationHelper.TypeShape,
        kdb.Shape: kdb.PCellDeclarationHelper.TypeShape,
        kdb.PCellDeclarationHelper.TypeList: kdb.PCellDeclarationHelper.TypeList,
        "TypeList": kdb.PCellDeclarationHelper.TypeList,
        "list": kdb.PCellDeclarationHelper.TypeList,
        list: kdb.PCellDeclarationHelper.TypeList,
        Optional[list]: kdb.PCellDeclarationHelper.TypeList,
    }
    try:
        annotation = param.annotation
        if annotation is Parameter.empty:
            annotation = type(param.default)
    except AttributeError:
        annotation = param
    if not annotation in type_map:
        raise ValueError(
            f"Cannot create pcell. Parameter {param.name!r} has unsupported type: {annotation!r}"
        )
    return type_map[annotation]

# Python type -> Klayout PCell type
def _python_type(param: Parameter):
    type_map = {
        kdb.PCellDeclarationHelper.TypeInt: int,
        "TypeInt": int,
        "int": int,
        int: int,
        kdb.PCellDeclarationHelper.TypeDouble: float,
        "TypeDouble": float,
        "float": float,
        float: float,
        kdb.PCellDeclarationHelper.TypeString: str,
        "TypeString": str,
        "str": str,
        str: str,
        kdb.PCellDeclarationHelper.TypeBoolean: bool,
        "TypeBoolean": bool,
        "bool": bool,
        bool: bool,
        kdb.PCellDeclarationHelper.TypeLayer: kdb.LayerInfo,
        "TypeLayer": kdb.LayerInfo,
        "LayerInfo": kdb.LayerInfo,
        kdb.LayerInfo: kdb.LayerInfo,
        kdb.PCellDeclarationHelper.TypeShape: kdb.Shape,
        "TypeShape": kdb.Shape,
        "Shape": kdb.Shape,
        kdb.Shape: kdb.Shape,
        kdb.PCellDeclarationHelper.TypeList: list,
        "TypeList": list,
        "list": list,
        list: list,
    }
    try:
        annotation = param.annotation
        if annotation is Parameter.empty:
            annotation = type(param.default)
    except AttributeError:
        annotation = param
    if not annotation in type_map:
        raise ValueError(
            f"Cannot create pcell. Parameter {param.name!r} has unsupported type: {annotation!r}"
        )
    return type_map[annotation]

def _validate_on_error(on_error:str):
    on_error = on_error.lower()
    if not on_error in ["raise", "ignore"]:
        raise ValueError("on_error should be 'raise' or 'ignore'.")
    return on_error

def _validate_parameter(name:str, param: Parameter):
    if param.kind == Parameter.VAR_POSITIONAL:
        raise ValueError(
            f"Cannot create pcell from functions with var positional [*args] arguments."
        )
    elif param.kind == Parameter.VAR_KEYWORD:
        raise ValueError(
            f"Cannot create pcell from functions with var keyword [**kwargs] arguments."
        )
    elif param.kind == Parameter.POSITIONAL_ONLY:
        raise ValueError(
            f"Cannot create pcell from functions with positional arguments. Please use keyword arguments."
        )
    elif (param.kind == Parameter.POSITIONAL_OR_KEYWORD) and (param.default is Parameter.empty):
        raise ValueError(
            f"Cannot create pcell from functions with positional arguments. Please use keyword arguments."
        )
    annotation = _python_type(_klayout_type(_python_type(param)))
    default = param.default
    try:
        default = annotation(default)
    except Exception:
        pass
    return Parameter(
        name,
        kind=Parameter.KEYWORD_ONLY,
        default=default,
        annotation=annotation,
    )
