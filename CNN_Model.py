from argparse import ArgumentParser
from distutils.util import strtobool
from os.path import exists

from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import StochasticWeightAveraging, EarlyStopping
from pytorch_lightning.loggers import TensorBoardLogger
from torch import nn
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau

from ADNI_Image_Module import ADNI_Image_Module
from ADNI_Model import ADNI_Model
from Repeated_CV_Splitter import get_adhc_split_csvs


# Somewhat closely modeled after this paper: http://dx.doi.org/10.1101/2021.09.09.21263013
class ADNI_CNN_Model(ADNI_Model):
    def __init__(self):
        super().__init__()
        self.num_classes = 2

        self.conv_part = nn.Sequential(
            self._conv_layer_set(1, 16, 5, 1),
            self._conv_layer_set(16, 16, 5, 2),
            self._conv_layer_set(16, 16, 3, 1),
            self._conv_layer_set(16, 16, 3, 2),
            self._conv_layer_set(16, 16, 3, 1),
            self._conv_layer_set(16, 16, 3, 2),
            self._conv_layer_set(16, 16, 3, 1),
            self._conv_layer_set(16, 16, 3, 2),
            nn.Flatten(),
        )

        self.feature_extractor_fully_connected = nn.Sequential(
            nn.Dropout(p=0.5),
            nn.Linear(8192, 32),
            nn.ReLU(),
            nn.Dropout(p=0.5)
        )

        self.feature_extractor = nn.Sequential(self.conv_part, self.feature_extractor_fully_connected)
        self.classifier = nn.Linear(32, self.num_classes if self.num_classes > 2 else 1)
        self.model = nn.Sequential(self.feature_extractor, self.classifier)

    @staticmethod
    def _conv_layer_set(in_c, out_c, ks, strides):
        conv_layer = nn.Sequential(
            nn.Conv3d(in_c, out_c, kernel_size=(ks, ks, ks), padding=0, stride=strides),
            nn.ReLU(),
        )
        return conv_layer

    def configure_optimizers(self):
        optimizer = Adam(self.parameters(), lr=1e-4)

        lr_scheduler = ReduceLROnPlateau(optimizer, patience=10, factor=0.5, verbose=True)

        scheduler = {
            'scheduler': lr_scheduler,
            'reduce_on_plateau': True,
            # val_checkpoint_on is val_loss passed in as checkpoint_on
            'monitor': 'loss/val'
        }
        return [optimizer], [scheduler]

    def __str__(self):
        return 'Tiny-ADNI-CNN2'


def get_CNN_chkpt_file(chkpt_dir, CNN_type, split_var, ratio, run_idx, fold, test):
    if CNN_type == 'CNN':
        chkpt_file = chkpt_dir + 'ADNI_tCNN'
    else:
        chkpt_file = chkpt_dir + 'ADNI_3slice_CNN'

    if split_var == 0:
        chkpt_file = chkpt_file + "_Sex"
    else:
        chkpt_file = chkpt_file + "_AgeGroup"

    chkpt_file = chkpt_file + f'-ratio={ratio:.2f}-run={run_idx}-fold={fold}'

    if test:
        chkpt_file = chkpt_file + '_fake'

    chkpt_file = chkpt_file + '.ckpt'

    return chkpt_file


if __name__ == '__main__':
    parser = ArgumentParser()
    # nargs="+" enables multi-gpu, but we don't want that because results differed when using different amounts of gpus.
    parser.add_argument("-g", "--gpu", dest="gpu", default=7, help="GPU to use", type=int)
    parser.add_argument("-r", "--ratio", dest="ratio", default=0.5,
                        help="Ratio of females in training dataset", type=float)
    parser.add_argument("-i", "--run_idces", dest="run_idces", default=[0, 1, 2, 3, 4], nargs="+",
                        help="Run idces to iterate over", type=int)
    parser.add_argument("-e", "--export_path", dest="export_path", default=None, type=str)
    parser.add_argument("-f", "--fold", dest="fold", default=0, type=int)
    # train on images with female AD images set to all-black, to test training + the whole pipeline
    parser.add_argument("-t", "--test", dest="fake_diffs", default=False, type=lambda x: bool(strtobool(x)))
    # split_var=0 == Sex, split_var=1 == Age
    parser.add_argument("-s", "--split_var", dest="split_var", default=0, type=int)
    parser.add_argument("-a", "--feature_csv_dir", dest="feature_csv_dir", type=str, default="")
    parser.add_argument("-d", "--split_dir", dest="split_dir", type=str, default="./splits/")
    parser.add_argument("-l", "--log_dir", dest="log_dir", type=str, default="./CNN-logs/")
    parser.add_argument("-c", "--chkpt_dir", dest="chkpt_dir", type=str,
                        default="./CNN-chkpts/")
    args = parser.parse_args()

    assert (isinstance(args.ratio, float))

    if args.split_var == 0:
        split_var = 'Sex'
    elif args.split_var == 1:
        split_var = 'AgeGroup'

    # Yes, the ADNI3 images are in the ADNI1 directory for some reason
    # image_paths = ["/scratch/ewipe/freesurfer_ADNI1",
    #                "/scratch/ewipe/freesurfer_ADNI2",
    #                "/scratch/ewipe/freesurfer_ADNI1"]

    image_paths = ["./normalized/ADNI1/",
                   "./normalized/ADNI2/",
                   "./normalized/ADNI1/"]

    for run_idx in args.run_idces:

        chkpt_file = get_CNN_chkpt_file(args.chkpt_dir, 'CNN', args.split_var, args.ratio, run_idx, args.fold,
                                        args.fake_diffs)

        if not exists(chkpt_file):
            if args.fake_diffs:
                log_name = f'tCNN_{split_var}-r{args.ratio:.2f}_fake'
            else:
                log_name = f'tCNN_{split_var}-r{args.ratio:.2f}'

            adhc_split_csvs = get_adhc_split_csvs(split_var, run_idx, args.ratio, args.fold, split_dir=args.split_dir)
            tb_logger = TensorBoardLogger(args.log_dir, name=log_name, version=f'test set {run_idx}, fold {args.fold}')

            adni1_dm = ADNI_Image_Module(image_paths=image_paths, adni_set=3, batch_size=6, adhc_split_csvs=adhc_split_csvs, increased_aug=True,
                                         export_path=args.export_path, fake_diff=args.fake_diffs,
                                         feature_csv_dir=args.feature_csv_dir)

            mdl = ADNI_CNN_Model()

            trainer = Trainer(
                logger=tb_logger,
                max_epochs=200,
                #gpus=[args.gpu],
                precision=16,
                callbacks=[StochasticWeightAveraging(swa_lrs=5e-4), EarlyStopping(monitor="loss/val", patience=60)],
                gradient_clip_val=1.0,
                enable_checkpointing=False,
                log_every_n_steps=26,
                accelerator='cpu',
                devices=1)

            trainer.fit(mdl, adni1_dm)
            trainer.save_checkpoint(chkpt_file)
